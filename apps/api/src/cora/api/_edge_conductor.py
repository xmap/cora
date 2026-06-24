"""Composition-root edge conductor: terminalize ANY aggregate FSM over a port.

`EdgeConductor` is the ONE L2 edge-runtime shell the composition root
hosts. It conducts an aggregate (a Run, or a Procedure phase) to its
terminal across a substrate port, generalising what the Procedure
`Conductor` (over `ControlPort`) and the now-dissolved Reckoner (over
`ComputePort`) each did with their own near-identical `conduct()` spine.

## What it unifies

The two spines reduced to ONE shape modulo (a) the inner work primitive
and (b) whether the engine owns the start transition. `EdgeConductor`
captures the shared shell:

    optional start  ->  inner work (yields a ConductOutcome)  ->  terminal

and drives EITHER FSM by INJECTING the parts that genuinely diverge,
never hardcoding one aggregate:

- **`start`** (`Optional`): a Procedure phase issues `start_procedure`
  inside the conduct; a Run passes NONE (`start_run` is the heavy gated
  entry that must not fold in, so the caller starts the Run upstream).
- **`complete` / `abort`** (the terminalize pair): each is an injected
  builder that, given the inner `ConductOutcome`, issues its FSM's
  terminal command. The complete arm carries the success provenance; the
  abort arm is best-effort. The `artifact_uri` asymmetry lives in the
  injected builders: a Run's complete arm carries it, its abort arm does
  not, so the two arms build DIFFERENT commands, not one shared bag.
- **`reraise`** (a per-FSM exception set): the Procedure path re-raises a
  closed lifecycle set (`UnauthorizedError` / `ProcedureNotFoundError` /
  `ConcurrencyError` -> 403/404/409 route mappers); the Run path catches
  broadly (an EMPTY set), matching the dissolved Reckoner. The engine
  carries BOTH as injected sets, never hardcoding one.

## The two kind-sources are preserved

The actuation kind the engine threads onto the terminal comes from the
INNER work, never from the engine: a control-step conduct derives it
through the Procedure Conductor's `_ActuationObserver`; a compute conduct
derives it from `ComputePort.provide_result(...).actuation_kind`. The
engine is agnostic; the inner work hands it a `ConductOutcome` already
carrying the observed kind, and the injected terminalize builders read it
back off the concrete outcome.

## Why it lives at `cora.api`

It needs both `ComputePort` (`cora.operation`-owned) and the Run FSM
handlers (`cora.run.features`). tach forbids `cora.run -> cora.operation`,
and Operation imports only `cora.run.aggregates`, so no BC can host a
runtime that needs both. `cora.api` is the one module that depends on
both, exactly as the dissolved Reckoner did. The merge is a code
consolidation, not a layering move and not a BC merge: the Run and
Procedure AGGREGATES stay separate.

## Single-blocking, cancel-orphan-safe

The inner work completes within one `conduct()` call (no intermediate
FSM state). A cancelled conduct best-effort aborts the aggregate via the
shared `abort_orphan_on_cancel`, then re-raises, so a cancelled conduct
never strands the FSM in `Running`. The guard wraps the WHOLE inner work
(submit + await + fetch), not only the await: a DELIBERATE strengthening
over the dissolved Reckoner, which guarded `await_terminal_state` alone.
So a cancel during submit, or during the post-success artifact fetch, also
terminalizes the aggregate (Aborted) instead of leaving a Run `Running`;
the trade is that a job that succeeded just before a mid-fetch cancel is
aborted rather than left recoverable (the stronger never-strand invariant
wins). Behaviour is otherwise byte-for-byte the dissolved Reckoner's. The
fire-and-reconcile split (submit returns immediately; a reconciler
completes later) is the second-substrate (Slurm) trigger, deferred.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from cora.infrastructure.edge_runtime import abort_orphan_on_cancel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.ports.compute_port import (
    ArtifactNotFoundError,
    ComputeJobFailedError,
    ComputeNotAvailableError,
    ComputeStatus,
    ComputeSubmitRejectedError,
    ComputeTimeoutError,
)
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.complete_run.command import CompleteRun

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from cora.infrastructure.edge_runtime import ConductOutcome
    from cora.operation.ports.compute_port import (
        ArtifactRef,
        ComputePort,
        JobId,
        JobSpec,
    )
    from cora.operation.ports.control_port import ActuationKind
    from cora.run.features.abort_run.handler import Handler as AbortRunHandler
    from cora.run.features.complete_run.handler import Handler as CompleteRunHandler

# Bound so a derived abort reason always fits RunAbortReason (1-500
# chars after trim); the substrate detail tail is truncated to leave
# headroom for the prefix.
_REASON_MAX = 480


class EdgeConductor[OutcomeT: ConductOutcome]:
    """The composition-root edge-runtime shell: optional-start -> work -> terminal.

    Construct once per driven FSM with the injected handlers; call
    `conduct` per episode. It drives EITHER FSM:

    - a Run (`start=None`, empty `reraise`, `complete`/`abort` build the
      Run terminals carrying the `artifact_uri` asymmetry);
    - a Procedure phase (`start` issues `start_procedure`, `reraise` is the
      lifecycle set, `complete`/`abort` build the Procedure terminals).

    The shell owns ONLY the cross-FSM control flow: the optional start, the
    cancel-orphan-safe inner await, the success/failure terminalize branch,
    and the per-FSM reraise policy. Everything FSM-specific is injected.
    """

    def __init__(
        self,
        *,
        start: Callable[[], Awaitable[object]] | None,
        complete: Callable[[OutcomeT], Awaitable[OutcomeT]],
        abort: Callable[[OutcomeT], Awaitable[OutcomeT]],
        cancel_abort: Callable[[], Awaitable[object]],
        reraise: tuple[type[Exception], ...],
    ) -> None:
        self._start = start
        self._complete = complete
        self._abort = abort
        self._cancel_abort = cancel_abort
        self._reraise = reraise

    async def conduct(self, inner: Callable[[], Awaitable[OutcomeT]]) -> OutcomeT:
        """Conduct one episode: optional start -> `inner` -> terminalize.

        `inner` performs the FSM-specific work (submit/await/fetch for a
        compute Run; the Conductor's step walk for a Procedure phase) and
        returns its concrete `ConductOutcome`. The shell then completes on
        success or best-effort aborts on failure, returning the terminalize
        builder's (possibly amended) outcome - a complete-terminal rejection
        becomes a failure on the returned outcome.

        The injected `start` re-raises its FSM's lifecycle set
        (`UnauthorizedError` / not-found / concurrency) so the route layer
        maps them to 403/404/409; a non-lifecycle start rejection is the
        builder's concern. A `CancelledError` while `inner` runs best-effort
        aborts via the injected `cancel_abort` and re-raises, so the FSM is
        never stranded in `Running` by a cancellation.
        """
        if self._start is not None:
            try:
                await self._start()
            except self._reraise:
                raise
        async with abort_orphan_on_cancel(self._cancel_abort):
            outcome = await inner()
        if outcome.succeeded:
            return await self._complete(outcome)
        # Best-effort abort: a failed conduct's diagnostic must survive even
        # if the FSM cannot be transitioned (already terminal); the injected
        # abort suppresses its own rejection. The lifecycle reraise set lets a
        # Procedure surface 403/404/409 mappers while a Run (empty set)
        # catches broadly.
        return await self._abort(outcome)


@dataclass(frozen=True)
class RunConductOutcome:
    """Outcome of conducting a single compute Run via `EdgeConductor`.

    `status` is the job's terminal `ComputeStatus`, or None when the job
    never started (submit was rejected / the substrate was unavailable).
    `job_id` / `artifact_ref` / `actuation_kind` carry the captured
    provenance (artifact only on success). `failure` is the abort reason
    recorded on the Run when the conduct did not succeed, or a
    lifecycle-handler error message when the terminal transition itself
    was rejected; None on a clean success.

    Structurally satisfies the `ConductOutcome` Protocol
    (`succeeded` + `actuation_kind`) so the shell treats it uniformly.
    """

    run_id: UUID
    status: ComputeStatus | None
    job_id: JobId | None = None
    artifact_ref: ArtifactRef | None = None
    actuation_kind: ActuationKind | None = None
    failure: str | None = None

    @property
    def succeeded(self) -> bool:
        # Key on is_success (the single source of truth shared with the fetch
        # gate in _run_compute) rather than `is SUCCEEDED`, so a future
        # non-SUCCEEDED success status cannot route a fetched artifact to abort.
        return self.status is not None and self.status.is_success and self.failure is None


class ComputeRunDriver:
    """Conduct a compute Run to its terminal over `ComputePort`.

    The compute inner-work + Run terminalizers the `EdgeConductor` shell
    drives for a Run: submit -> await -> fetch, then `complete_run`
    (carrying the captured provenance + artifact uri) on success, or
    best-effort `abort_run` on failure. The Run carries NO start seam
    (start_run is the gated entry upstream) and an EMPTY reraise set
    (catch broadly), matching the dissolved Reckoner.

    This is the dual-reader (REST + MCP) Run-conduct entry. A multi-step
    compute Run is conducted as a Procedure PHASE of the Run instead,
    via the `conduct_phase_then_complete_run` glue; a single-job Run is
    the degenerate case this driver keeps inline (one submit/await/fetch),
    so the floor does not force a Procedure phase onto the bare endpoint.
    """

    def __init__(
        self,
        *,
        compute_port: ComputePort,
        complete_run: CompleteRunHandler,
        abort_run: AbortRunHandler,
    ) -> None:
        self._compute_port = compute_port
        self._complete_run = complete_run
        self._abort_run = abort_run

    async def conduct(
        self,
        *,
        run_id: UUID,
        job_spec: JobSpec,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunConductOutcome:
        """Conduct an already-`Running` compute Run to its terminal.

        Submits `job_spec`, awaits the terminal state, and transitions the
        Run via the `EdgeConductor` shell: `complete_run` (provenance +
        artifact uri) on `Succeeded`, else best-effort `abort_run`. A
        `CancelledError` mid-conduct best-effort aborts the Run and
        re-raises.
        """
        envelope: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }
        # Holds the in-flight job id once submit returns, so the
        # cancel-orphan abort (built before the job is known) can record it
        # as a breadcrumb. None until submit succeeds (a cancellation during
        # submit thus records no job id).
        in_flight: list[JobId] = []
        engine: EdgeConductor[RunConductOutcome] = EdgeConductor(
            # No start seam for a Run (start_run is the gated entry upstream).
            start=None,
            complete=lambda outcome: self._issue_complete(run_id, outcome, envelope),
            abort=lambda outcome: self._issue_abort(run_id, outcome, envelope),
            # Cancel-orphan abort: a conduct cancelled mid-flight leaves the
            # Run `Running` with a job in an unknown state. The observed kind
            # is unrecoverable on cancellation, so this records None.
            cancel_abort=lambda: self._abort_run(
                AbortRun(
                    run_id=run_id,
                    reason="cancelled mid-compute",
                    actuation_kind=None,
                    producing_job_id=str(in_flight[0]) if in_flight else None,
                ),
                **envelope,
            ),
            # Run catches broadly (empty set), exactly as the Reckoner did.
            reraise=(),
        )
        return await engine.conduct(lambda: self._run_compute(run_id, job_spec, in_flight))

    async def _run_compute(
        self, run_id: UUID, job_spec: JobSpec, in_flight: list[JobId]
    ) -> RunConductOutcome:
        """Inner work: submit -> await -> fetch, mapping failures to an outcome.

        Returns a non-succeeded `RunConductOutcome` (the shell then
        best-effort aborts) for any compute failure family, or a succeeded
        outcome carrying the artifact + provenance the shell completes with.
        Job-id provenance rides the outcome so the shell's abort builder
        records it; the cancel path records the in-flight id (kind
        unrecoverable, so None there).
        """
        try:
            job_id = await self._compute_port.submit(job_spec)
        except (ComputeSubmitRejectedError, ComputeNotAvailableError) as exc:
            return RunConductOutcome(
                run_id=run_id,
                status=None,
                failure=_bounded(f"compute submit failed: {exc}"),
            )
        in_flight.append(job_id)
        try:
            status = await self._compute_port.await_terminal_state(job_id)
        except ComputeTimeoutError as exc:
            return self._failure_outcome(run_id, job_id, ComputeStatus.TIMED_OUT, str(exc))
        except ComputeJobFailedError as exc:
            return self._failure_outcome(run_id, job_id, ComputeStatus.FAILED, str(exc))
        if not status.is_success:
            return self._failure_outcome(run_id, job_id, status, _status_reason(status))
        try:
            artifact_ref = await self._compute_port.fetch_artifact_ref(job_id)
        except ArtifactNotFoundError as exc:
            return self._failure_outcome(run_id, job_id, status, str(exc))
        result = self._compute_port.provide_result(job_id, status, (artifact_ref,))
        return RunConductOutcome(
            run_id=run_id,
            status=status,
            job_id=job_id,
            artifact_ref=artifact_ref,
            actuation_kind=result.actuation_kind,
        )

    def _failure_outcome(
        self, run_id: UUID, job_id: JobId, status: ComputeStatus, detail: str
    ) -> RunConductOutcome:
        """A non-success outcome carrying the captured kind + bounded reason."""
        result = self._compute_port.provide_result(job_id, status, ())
        return RunConductOutcome(
            run_id=run_id,
            status=status,
            job_id=job_id,
            actuation_kind=result.actuation_kind,
            failure=_bounded(detail),
        )

    async def _issue_complete(
        self, run_id: UUID, outcome: RunConductOutcome, envelope: dict[str, Any]
    ) -> RunConductOutcome:
        """The Run complete arm: CompleteRun carries the artifact_uri (asymmetry).

        A complete-terminal rejection is NOT swallowed: it is recorded on
        the returned outcome's `failure` so the caller sees "the conduct
        succeeded but the Run could not be completed."
        """
        assert outcome.artifact_ref is not None  # success implies an artifact
        try:
            await self._complete_run(
                CompleteRun(
                    run_id=run_id,
                    actuation_kind=(
                        outcome.actuation_kind.value if outcome.actuation_kind is not None else None
                    ),
                    producing_job_id=str(outcome.job_id) if outcome.job_id is not None else None,
                    artifact_uri=outcome.artifact_ref.uri,
                ),
                **envelope,
            )
        except Exception as exc:  # lifecycle handler rejected the complete
            return replace(outcome, failure=_bounded(f"complete_run rejected: {exc}"))
        return outcome

    async def _issue_abort(
        self, run_id: UUID, outcome: RunConductOutcome, envelope: dict[str, Any]
    ) -> RunConductOutcome:
        """The Run abort arm: AbortRun, swallowing a lifecycle rejection.

        AbortRun carries NO `artifact_uri` (a failed job's partial output is
        not registered) - the artifact_uri asymmetry. Best-effort: if the
        abort ALSO fails (the Run was already terminal), the original
        conduct failure is what the caller sees on the returned outcome. The
        Run path's empty reraise set means even a lifecycle-mapped exception
        is suppressed here, matching the dissolved Reckoner's broad catch.
        """
        with contextlib.suppress(Exception):
            await self._abort_run(
                AbortRun(
                    run_id=run_id,
                    reason=outcome.failure or "compute conduct failed",
                    actuation_kind=(
                        outcome.actuation_kind.value if outcome.actuation_kind is not None else None
                    ),
                    producing_job_id=str(outcome.job_id) if outcome.job_id is not None else None,
                ),
                **envelope,
            )
        return outcome


_STATUS_REASON = {
    ComputeStatus.FAILED: "compute job failed",
    ComputeStatus.CANCELLED: "compute job cancelled",
    ComputeStatus.TIMED_OUT: "compute job timed out",
}


def _status_reason(status: ComputeStatus) -> str:
    """Abort reason for a non-success terminal status."""
    return _STATUS_REASON.get(status, f"compute job ended {status.value}")


def _bounded(text: str) -> str:
    """Trim a derived abort reason to fit RunAbortReason's 1-500 bound."""
    trimmed = text.strip()
    if len(trimmed) <= _REASON_MAX:
        return trimmed
    return trimmed[: _REASON_MAX - 3] + "..."


__all__ = ["ComputeRunDriver", "EdgeConductor", "RunConductOutcome"]
