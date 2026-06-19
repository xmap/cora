"""Composition-root runtime: conduct a compute Run via ComputePort.

`ComputeRuntime` is the CONDUCT-side L2 edge runtime for compute Runs,
peer to the Operation BC's Procedure `Conductor`. The Conductor drives
a Procedure FSM via `ControlPort`; this drives a Run FSM via
`ComputePort`. It submits a compute job, awaits its terminal state,
captures the artifact + provenance, and transitions the Run
(`complete_run` on success, `abort_run` on failure), threading the
conduct-observed `ActuationKind` + job id onto the terminal event for
replay-deterministic provenance ([[project_non_determinism_principle]]).

## Why it lives at the composition root

`ComputePort` is Operation-BC-owned (`cora.operation.ports`) and the
Run FSM handlers are Run-BC-owned (`cora.run.features`). tach forbids
`cora.run -> cora.operation`, and Operation imports only
`cora.run.aggregates` (not Run features), so neither BC can host a
runtime that needs both. `cora.api` is the one module that depends on
both, exactly as `ControlPortEnclosureObserver` bridges Enclosure +
Operation here. If a third cross-BC ComputePort/ControlPort consumer
appears, the rule-of-three move is to hoist the port to
`cora.infrastructure.ports` and relocate the runtime into a BC
`adapters/` package.

## Execution model (single blocking conduct)

`submit` then `await_terminal_state` complete one job within one
`conduct()` call; no intermediate Run FSM state is introduced (the Run
stays `Running` for the duration, exactly as `start_run` left it). The
fire-and-reconcile split (submit returns immediately; a separate
reconciler completes the Run) is the second-adapter (Slurm) trigger,
deferred. A cancelled conduct best-effort aborts the Run and re-raises,
mirroring the Conductor's `CancelledError` handling.

## Genesis ownership

The runtime conducts an already-`Running` Run; it does NOT start the
Run. `start_run` stays the normal gated entry (it runs the cross-BC
clearance / enclosure / supply gates the runtime must not bypass). The
caller starts the Run, then hands its id here to conduct.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
    from uuid import UUID

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


@dataclass(frozen=True)
class ComputeRunResult:
    """Outcome of a `ComputeRuntime.conduct` call.

    `status` is the job's terminal `ComputeStatus`, or None when the
    job never started (submit was rejected / the substrate was
    unavailable). `job_id` / `artifact_ref` / `actuation_kind` carry
    the captured provenance (artifact only on success). `failure` is
    the abort reason recorded on the Run when the conduct did not
    succeed, or a lifecycle-handler error message when the terminal
    transition itself was rejected; None on a clean success.
    """

    run_id: UUID
    status: ComputeStatus | None
    job_id: JobId | None = None
    artifact_ref: ArtifactRef | None = None
    actuation_kind: ActuationKind | None = None
    failure: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is ComputeStatus.SUCCEEDED and self.failure is None


class ComputeRuntime:
    """Drive one compute Run's conduct: submit -> await -> complete | abort."""

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
    ) -> ComputeRunResult:
        """Conduct an already-`Running` Run to its terminal via ComputePort.

        Submits `job_spec`, awaits the terminal state, and transitions
        the Run: `complete_run` (carrying the captured provenance) on
        `Succeeded`, else best-effort `abort_run` with a reason derived
        from the failure. A `CancelledError` mid-conduct best-effort
        aborts the Run and re-raises so the caller's task still sees the
        cancellation.
        """
        envelope: dict[str, Any] = {
            "principal_id": principal_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "surface_id": surface_id,
        }

        # --- submit: a substrate-level failure means no job ever ran ---
        try:
            job_id = await self._compute_port.submit(job_spec)
        except (ComputeSubmitRejectedError, ComputeNotAvailableError) as exc:
            reason = _bounded(f"compute submit failed: {exc}")
            await self._best_effort_abort(run_id, reason, None, None, envelope)
            return ComputeRunResult(run_id=run_id, status=None, failure=reason)

        # --- await terminal state ---
        try:
            status = await self._compute_port.await_terminal_state(job_id)
        except asyncio.CancelledError:
            # Conduct cancelled mid-flight (caller cancelled the task or
            # the loop is shutting down). The Run is Running with a job
            # in an unknown state; best-effort abort so operator state
            # reflects the cancellation, then re-raise (signals + shutdown
            # behave normally). Observed kind is unrecoverable here.
            with contextlib.suppress(Exception):
                await self._abort_run(
                    AbortRun(
                        run_id=run_id,
                        reason="cancelled mid-compute",
                        actuation_kind=None,
                        producing_job_id=str(job_id),
                    ),
                    **envelope,
                )
            raise
        except ComputeTimeoutError as exc:
            return await self._abort_conduct(
                run_id, job_id, ComputeStatus.TIMED_OUT, str(exc), envelope
            )
        except ComputeJobFailedError as exc:
            return await self._abort_conduct(
                run_id, job_id, ComputeStatus.FAILED, str(exc), envelope
            )

        if not status.is_success:
            return await self._abort_conduct(
                run_id, job_id, status, _status_reason(status), envelope
            )

        # --- success: fetch artifact, capture provenance, complete ---
        try:
            artifact_ref = await self._compute_port.fetch_artifact_ref(job_id)
        except ArtifactNotFoundError as exc:
            return await self._abort_conduct(run_id, job_id, status, str(exc), envelope)

        provenance = self._compute_port.provide_provenance_payload(job_id, status, artifact_ref)
        try:
            await self._complete_run(
                CompleteRun(
                    run_id=run_id,
                    actuation_kind=provenance.actuation_kind.value,
                    producing_job_id=str(job_id),
                    artifact_uri=artifact_ref.uri,
                ),
                **envelope,
            )
        except Exception as exc:  # lifecycle handler rejected the complete
            return ComputeRunResult(
                run_id=run_id,
                status=status,
                job_id=job_id,
                artifact_ref=artifact_ref,
                actuation_kind=provenance.actuation_kind,
                failure=_bounded(f"complete_run rejected: {exc}"),
            )
        return ComputeRunResult(
            run_id=run_id,
            status=status,
            job_id=job_id,
            artifact_ref=artifact_ref,
            actuation_kind=provenance.actuation_kind,
        )

    async def _abort_conduct(
        self,
        run_id: UUID,
        job_id: JobId,
        status: ComputeStatus,
        detail: str,
        envelope: dict[str, Any],
    ) -> ComputeRunResult:
        """Capture provenance for a failed job and best-effort abort the Run."""
        provenance = self._compute_port.provide_provenance_payload(job_id, status, None)
        reason = _bounded(detail)
        await self._best_effort_abort(
            run_id, reason, provenance.actuation_kind.value, str(job_id), envelope
        )
        return ComputeRunResult(
            run_id=run_id,
            status=status,
            job_id=job_id,
            actuation_kind=provenance.actuation_kind,
            failure=reason,
        )

    async def _best_effort_abort(
        self,
        run_id: UUID,
        reason: str,
        actuation_kind: str | None,
        producing_job_id: str | None,
        envelope: dict[str, Any],
    ) -> None:
        """Abort the Run, swallowing a lifecycle rejection.

        The abort is best-effort: if it ALSO fails (e.g. the Run was
        already terminal), the original conduct failure is what the
        caller sees on the result; the Run stays as-is and the operator
        reconciles via state inspection. Mirrors the Conductor's
        best-effort abort.
        """
        with contextlib.suppress(Exception):
            await self._abort_run(
                AbortRun(
                    run_id=run_id,
                    reason=reason,
                    actuation_kind=actuation_kind,
                    producing_job_id=producing_job_id,
                ),
                **envelope,
            )


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


__all__ = ["ComputeRunResult", "ComputeRuntime"]
