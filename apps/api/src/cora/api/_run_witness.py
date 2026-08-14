"""RunWitness runtime: shadow-observe an external tool's captures, and
(behind a second, independent kill switch) promote a BEGUN capture to a
real witnessed Run.

Background loop draining a `CaptureObserver` and logging each
observation's classified phase. Shadow mode (the default, and the only
behavior until `Settings.run_witness_recording_enabled` is turned on)
writes nothing anywhere, ever: no event append, no entries-table write,
no Run command issued. When recording is enabled, a `BEGUN` observation
for a capture with no open Run promotes one via `record_witnessed_run`,
with per-capture-code dedup so a single in-progress capture is never
promoted twice (see `RunWitnessRecorder`).

Hosted at the composition root (`cora.api`), like `_run_initiator.py`
and `_enclosure_permit_observer.py`: it composes a Run BC command with
an Agent principal, and only `cora.api` may depend on both.

## Log lines, one per observation

- `run_witness.capture_begun`
- `run_witness.capture_progressing`
- `run_witness.capture_ended`
- `run_witness.capture_aborted`
- `run_witness.capture_unrecognized`: `phase` is `UNRECOGNIZED`, meaning
  `reported_status` did not match the deployment's declared literal
  table. A vocabulary drift (a tool upgrade renaming a status), not
  routine progress; worth an operator's attention.
- `run_witness.capture_unreached`: `phase` is `None`, meaning this
  observation made no status claim at all (a probe-only re-affirmation
  read, or a disconnect the adapter reported with nothing to classify).

Every line carries `capture_code`, `reported_status`, `source_kind`,
`source_id`, and `observed_at` (nullable; see `CaptureObservation`'s
own docstring on why an adapter must never substitute a synthesized
time for an absent one). These log lines are unconditional: they fire
identically whether or not recording is enabled.

## Promotion (when run_witness_recording_enabled is True)

Per capture_code, a small dedup state machine:

  - `BEGUN` while no Run is open for this code: call `record_witnessed_run`
    and, on success, remember the returned run_id as OPEN. On failure
    (any raised error, including an authorization misconfiguration),
    log and stay unopened so the next `BEGUN` retries.
  - `BEGUN` while a Run is already open for this code: no-op (already
    promoted this capture cycle).
  - `ENDED` / `ABORTED` while a Run is open: clear the local dedup entry
    (log only, no Run action; terminal recording is a separate future
    slice).
  - `ENDED` / `ABORTED` while nothing is open, or `PROGRESSING` /
    `UNRECOGNIZED` / a `None` phase in any state: no-op.

`RunWitnessRecorder`'s dedup state is seeded once at boot (see
`rebuild_open_captures`) from every currently-Running Witnessed Run's
`external_refs`, so a still-open capture at process restart is never
re-promoted.

## Retry + resilience

Mirrors `run_enclosure_permit_monitor`: `observe()` ending (stream
terminated or raised) triggers a bounded sleep then re-subscribe. A
single bad observation is logged and skipped so the loop survives it.
Cancellation (lifespan shutdown) propagates.

## No startup-readiness gate

`enclosure_permit_monitor_lifespan` waits for a settled read before
yielding because a real precondition (the run-start preflight) reads
`permit_status` right after boot. Nothing downstream depends on this
runtime settling, so there is no boot race to close and no wait is
needed.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID
from cora.infrastructure.logging import get_logger
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs.query import ListRuns
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.ports.capture_observer import CaptureObserverScope, CapturePhase
from cora.shared.identity import MonitorSourceId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.infrastructure.config import Settings
    from cora.infrastructure.kernel import Kernel
    from cora.run.aggregates.run.state import Run
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.run.features.record_witnessed_run.handler import Handler as RecordWitnessedRunHandler
    from cora.run.ports.capture_observer import CaptureObservation, CaptureObserver
    from cora.shared.identifier import Identifier

_RECONNECT_DELAY_SECONDS = 5.0
_PAGE_LIMIT = 100
_CAPTURE_CODE_SCHEME = "capture-code"

_log = get_logger(__name__)

# Single hardcoded literal, mirroring `ENCLOSURE_PERMIT_MONITOR_SOURCE_ID`
# (`cora.enclosure._monitor`) exactly: there is exactly one in-process
# RunWitness per deployment, so no derivation function is needed.
RUN_WITNESS_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000072756e01"))

_PHASE_LOG_EVENT: dict[CapturePhase, str] = {
    CapturePhase.BEGUN: "run_witness.capture_begun",
    CapturePhase.PROGRESSING: "run_witness.capture_progressing",
    CapturePhase.ENDED: "run_witness.capture_ended",
    CapturePhase.ABORTED: "run_witness.capture_aborted",
    CapturePhase.UNRECOGNIZED: "run_witness.capture_unrecognized",
}

_TERMINAL_PHASES = (CapturePhase.ENDED, CapturePhase.ABORTED)


def observe_capture(observation: CaptureObservation) -> None:
    """Log one observation. The entire body of shadow mode: no writes."""
    if observation.phase is None:
        event = "run_witness.capture_unreached"
    else:
        event = _PHASE_LOG_EVENT[observation.phase]
    _log.info(
        event,
        capture_code=observation.capture_code,
        reported_status=observation.reported_status,
        source_kind=observation.source_kind,
        source_id=observation.source_id,
        observed_at=observation.observed_at.isoformat() if observation.observed_at else None,
    )


class RunWitnessRecorder:
    """Promotes a BEGUN observation to a witnessed Run when recording is
    enabled; a log-only pass-through (today's shadow behavior) otherwise.

    Internally tracks the per-capture-code dedup state: absence of a key
    means no Run is open for that capture; presence means the value is
    the open Run's id. Seeded once at construction from
    `rebuild_open_captures`, then owned exclusively by this instance for
    the process's lifetime.
    """

    def __init__(
        self,
        *,
        deps: Kernel,
        record_witnessed_run: RecordWitnessedRunHandler,
        settings: Settings,
        open_captures: dict[str, UUID] | None = None,
    ) -> None:
        self._deps = deps
        self._record_witnessed_run = record_witnessed_run
        self._settings = settings
        self._open_captures: dict[str, UUID] = dict(open_captures or {})

    async def observe_capture(self, observation: CaptureObservation) -> None:
        observe_capture(observation)
        if not self._settings.run_witness_recording_enabled:
            return

        code = observation.capture_code
        phase = observation.phase

        if phase is CapturePhase.BEGUN:
            if code in self._open_captures:
                return
            await self._promote(observation)
        elif phase in _TERMINAL_PHASES:
            run_id = self._open_captures.pop(code, None)
            if run_id is not None:
                _log.info("run_witness.open_capture_cleared", capture_code=code, run_id=str(run_id))
        # PROGRESSING, UNRECOGNIZED, and a None phase make no status
        # claim this state machine acts on: no-op regardless of state.

    async def _promote(self, observation: CaptureObservation) -> None:
        plan_id = self._settings.capture_watch_plan_id
        if plan_id is None:
            # Unreachable when `_enforce_run_witness_recording_gate`
            # (main.py) has run: it refuses to boot with recording
            # enabled and no plan_id set. Defensive no-op here so a
            # caller that constructs this class directly (tests) cannot
            # crash the loop instead of just not promoting.
            _log.error(
                "run_witness.recording_enabled_without_plan_id",
                capture_code=observation.capture_code,
            )
            return

        command = RecordWitnessedRun(
            name=f"Witnessed capture {observation.capture_code}",
            plan_id=plan_id,
            capture_code=observation.capture_code,
            monitor_source_id=RUN_WITNESS_MONITOR_SOURCE_ID,
            trigger="Monitor",
        )
        try:
            run_id = await self._record_witnessed_run(
                command,
                principal_id=RUN_WITNESS_AGENT_ID,
                correlation_id=self._deps.id_generator.new_id(),
            )
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            # Configuration fault: the RunWitness principal is not
            # granted RecordWitnessedRun. Log loudly; stay unopened so the
            # next BEGUN retries once the grant is fixed (same posture
            # as RunInitiator's StartRun grant).
            _log.warning(
                "run_witness.promotion_unauthorized",
                capture_code=observation.capture_code,
            )
            return
        except Exception:
            _log.exception(
                "run_witness.promotion_failed",
                capture_code=observation.capture_code,
            )
            return
        self._open_captures[observation.capture_code] = run_id
        _log.info(
            "run_witness.promoted",
            capture_code=observation.capture_code,
            run_id=str(run_id),
        )


def _extract_capture_code(external_refs: frozenset[Identifier]) -> str | None:
    """Find the `Identifier(scheme="capture-code", ...)` entry's value.

    Defensive: `record_witnessed_run`'s decider always stamps exactly one,
    so `None` should not happen for a Witnessed Run, but a missing ref
    must not crash the boot-time rebuild.
    """
    for ref in external_refs:
        if ref.scheme == _CAPTURE_CODE_SCHEME:
            return ref.value
    return None


async def rebuild_open_captures(deps: Kernel, *, list_runs: ListRunsHandler) -> dict[str, UUID]:
    """Page through every Running, Witnessed Run and return
    capture_code -> run_id for each one's `external_refs`.

    Seeds `RunWitnessRecorder`'s dedup state once at boot so a capture
    still open at process restart is never re-promoted. Mirrors
    `_run_supervisor._drain_runs` / `_run_initiator._drain_running_runs`'s
    exact paging shape.
    """
    from cora.run.aggregates.run.read import load_run

    open_captures: dict[str, UUID] = {}
    cursor: str | None = None
    while True:
        page = await list_runs(
            ListRuns(
                status="Running",
                conduct_mode="Witnessed",
                cursor=cursor,
                limit=_PAGE_LIMIT,
            ),
            principal_id=RUN_WITNESS_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
        )
        for item in page.items:
            run: Run | None = await load_run(deps.event_store, item.run_id)
            if run is None:
                continue
            capture_code = _extract_capture_code(run.external_refs)
            if capture_code is not None:
                open_captures[capture_code] = item.run_id
        if page.next_cursor is None:
            return open_captures
        cursor = page.next_cursor


async def run_witness_loop(
    *,
    observer: CaptureObserver,
    capture_codes: frozenset[str],
    recorder: RunWitnessRecorder | None = None,
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, logging (and, with a recorder, promoting)
    each observation; re-subscribe on stream end."""
    if not capture_codes:
        return
    scope = CaptureObserverScope(capture_codes=capture_codes)
    while True:
        try:
            async for observation in observer.observe(scope):
                try:
                    if recorder is not None:
                        await recorder.observe_capture(observation)
                    else:
                        observe_capture(observation)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception(
                        "run_witness.record_failed",
                        capture_code=observation.capture_code,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("run_witness.iteration_failed")
        await asyncio.sleep(reconnect_delay_seconds)


@contextlib.asynccontextmanager
async def run_witness_lifespan(
    *,
    observer: CaptureObserver,
    capture_codes: frozenset[str],
    deps: Kernel | None = None,
    record_witnessed_run: RecordWitnessedRunHandler | None = None,
    open_captures: dict[str, UUID] | None = None,
) -> AsyncGenerator[None]:
    """Run the watcher as a background task for the app's lifetime.

    No-op when `capture_codes` is empty: yields immediately without
    starting a task, mirroring `enclosure_permit_monitor_lifespan`'s
    no-op-when-unconfigured shape.

    `deps` stays optional (unlike the sibling `run_supervisor_lifespan`
    / `run_initiator_lifespan`, which require it) so every existing
    shadow-only caller needs no change: recording is the only thing that
    needs a Kernel (for id generation), so it is only required when
    `record_witnessed_run` is also supplied.
    """
    if not capture_codes:
        yield
        return
    if record_witnessed_run is not None and deps is None:
        msg = "run_witness_lifespan: record_witnessed_run requires deps"
        raise ValueError(msg)

    recorder: RunWitnessRecorder | None = None
    if record_witnessed_run is not None:
        assert deps is not None  # narrowed by the check above
        recorder = RunWitnessRecorder(
            deps=deps,
            record_witnessed_run=record_witnessed_run,
            settings=deps.settings,
            open_captures=open_captures,
        )

    task = asyncio.create_task(
        run_witness_loop(observer=observer, capture_codes=capture_codes, recorder=recorder),
        name="run-witness",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


__all__ = [
    "RUN_WITNESS_MONITOR_SOURCE_ID",
    "RunWitnessRecorder",
    "observe_capture",
    "rebuild_open_captures",
    "run_witness_lifespan",
    "run_witness_loop",
]
