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
`source_id`, and `observed_at` (nullable; see `CaptureLifecycleObservation`'s
own docstring on why an adapter must never substitute a synthesized
time for an absent one). These log lines are unconditional: they fire
identically whether or not recording is enabled.

## Promotion and termination (when run_witness_recording_enabled is True)

Per capture_code, a small dedup state machine:

  - `BEGUN` while no Run is open for this code: call `record_witnessed_run`
    and, on success, remember the returned run_id as OPEN. On failure
    (any raised error, including an authorization misconfiguration),
    log and stay unopened so the next `BEGUN` retries.
  - `BEGUN` while a Run is already open for this code: the previous
    terminal was missed (dropped CA transition, or the substrate
    restarted mid-capture). `TruncateRun` the stale Run first
    (`interrupted_at=None`: CORA does not know when it actually ended,
    only that it did not see the terminal), then promote the new
    capture as if idle. A truncate failure does not block the
    promotion: the new capture is a real fact regardless of whether the
    stale Run could be closed.
  - `ENDED` / `ABORTED` while a Run is open: call
    `record_witnessed_run_outcome` (`Ended` -> `RunCompleted`,
    `Aborted` -> `RunAborted`), carrying the observation's own
    `observed_at`. On success, clear the local dedup entry. On failure,
    leave the entry open: the next `BEGUN` for this code truncates it
    and promotes fresh, so the truncation path doubles as retry.
  - `ENDED` / `ABORTED` while nothing is open, or `PROGRESSING` /
    `UNRECOGNIZED` / a `None` phase in any state: no-op.

`RunWitnessRecorder`'s dedup state is seeded once at boot (see
`rebuild_open_captures`) from every currently-Running Witnessed Run's
`external_refs`, so a still-open capture at process restart is never
re-promoted.

## Closing the abort/success gap needs a deployment change too

`CaptureLifecycleObservation.phase` classifies the `status` role's literal off
the deployment's declared table, and separately, `ControlPortCaptureObserver`
now also reads an optional `abort` role: a decoded-asserted reading on
it is a direct `ABORTED` claim (see that module's docstring), landing
here as a terminal `_record_outcome` call ahead of whatever the
`status` PV says next. At 2-BM, `fly_scan()`'s exception handlers for
`ScanAbortError` / `CameraTimeoutError` / `FileOverwriteError` still
run `finally: self.end_scan()`, which writes the identical
`'Scan complete'` literal a genuine success writes.

The `abort` role only closes ONE of those three. `AbortScan` is written
only by `abort_scan()` (upstream `tomoscan.py`), itself reachable only
by an operator or automation writing to that PV directly; that is the
path that raises `ScanAbortError`. `CameraTimeoutError` and
`FileOverwriteError` write to NO PV at all before `end_scan()`'s
`'Scan complete'`, so no role this observer can subscribe to
distinguishes them from a genuine success (see tomography/tomoscan#181,
filed against this gap directly). `capture_progress_snapshot` on the
resulting `RunCompleted` is the complementary, deployment-independent
mitigation: the retained `collected` / `saved` counts are evidence a
reader can weigh even when no role fired, though (per that VO's own
docstring) they are evidence, never a verdict CORA computes itself.

The `abort` role's code capability exists as of the commit that added
it; the operator-abort slice of the gap only closes once a
deployment's `capture_watch_pvs` also declares the role for each code
(2-BM: `"abort": "2bmb:TomoScan:AbortScan"`). A code with no `abort`
entry watches `status` only, unchanged, so `ENDED` still unconditionally
maps to `RunCompleted` for it. Nothing in this file or in `Settings`
gates recording on the abort role being configured; the locked
deployment decision is to keep `run_witness_recording_enabled` off at
2-BM until both this effort's code and its own deployment config
change (adding the `abort` role) are live.

## Accepted residual: a reconnect can misread a still-open capture as new

The `BEGUN`-while-open heuristic assumes a second `BEGUN` for the same
code always means the prior terminal was missed. That is not quite
total: `camonitor`-style subscriptions deliver the PV's CURRENT value
immediately on a fresh subscribe (see `EpicsCaControlPort`), and the
observer resubscribes after every disconnect (see "Retry + resilience"
below). If a reconnect happens to land in the narrow window where the
substrate's status PV still genuinely reads the `BEGUN` literal for a
capture that has not actually restarted, this recorder cannot tell that
apart from a real new capture: it truncates the still-live Run
(spurious `RunTruncated`) and promotes a duplicate. The window is the
duration of one `BEGUN`-classified literal (milliseconds, per the
measured arcturus phase durations), and the outcome is a data-quality
degradation (an extra Run pair for one physical scan), not a control or
interlock concern. No narrower signal (comparing against the
last-observed reading, or `reach_tier`) is implemented; revisit if this
is ever observed in practice.

## Accepted residual: the `status` and `abort` pumps have no enforced ordering

`_capture_observer.py` runs the `status` and `abort` roles as two
independent pumps feeding one merged queue; nothing in this file or
that one enforces that an `ABORTED` reading is processed before a
later, causally-dependent `ENDED` reading from the other pump, only
that it usually will be, because 2-BM's own `abort_scan()` writes
`AbortScan` before its caller's `finally: end_scan()` writes
`ScanStatus`. This is a real ordering dependency on realistic,
network-driven CA delivery interleaving the two subscriptions fairly,
not a structural guarantee; a deliberately adversarial or bursty
delivery pattern (confirmed by constructing exactly this case against
a fake `ControlPort` that does not yield between readings, in
`test_run_witness_capture_replay.py`) could let the trailing `ENDED`
arrive first, in which case that capture records as `Completed` and
the correct `ABORTED` observation lands on the now-idle no-open-Run
path, a no-op. Same outcome, same severity, as the coalesced-abort
residual in `_capture_observer.py`'s own docstring: a real 2-BM abort
degrading to a `Completed` record, never a corrupted attribution to a
different Run.

## Accepted residual (slice 10): a post-restart missed terminal writes a trail into the wrong Run

The reconnect-during-BEGUN residual above already accepts that a
process restart mid-capture can leave a stale Run open with nothing to
truncate it until the NEXT capture's `BEGUN`. Before slice 10 that
window produced at most one wrong terminal event. With the progress
feeder wired, every flush tick during that window writes the NEW
capture's `images_saved` / `images_collected` readings into the STALE
Run's observation trail, because `rebuild_open_captures` seeds
`code -> stale_run_id` at boot and camonitor's first delivery on a
fresh subscribe is whatever literal the PV currently holds -- typically
a `PROGRESSING` one mid-capture, which triggers no `BEGUN` and so never
corrects the map. Detectable signature: the channel's value regresses
against the prior rows for the same Run instead of monotonically
increasing. Accepted rather than fixed here: closing it needs either a
staleness timer (explicitly out of scope per the locked slice-9
decision) or a monotonicity guard per (run_id, channel), which is a
real fix but a separate, deliberate design decision, not a wiring
change.

## Accepted residual (slice 10): CA's redeliver-on-resubscribe can misattribute a stale reading

If a reconnect lands between a new capture's `BEGUN` and its first
progress update, EPICS CA can redeliver the PREVIOUS capture's final
progress string with the PREVIOUS capture's own substrate timestamp on
the fresh subscribe. That reading is buffered under the current
capture_code and, having a real (if stale) `observed_at`, is not
skipped by the no-substrate-time guard; the next flush writes it
against the NEW Run, one row bearing an out-of-order timestamp lower
than the Run's own start. Same class as the reconnect-during-BEGUN
residual above (an artifact of CA's own resubscribe semantics, not a
bug in this code), and the same posture: a data-quality degradation
(one out-of-order row), never a claim this code cannot tell is
suspect. No freshness guard (rejecting a reading whose `observed_at`
predates the Run's own promotion) is implemented; it would need
threading a promotion timestamp through `RunWitnessRecorder`, a real
fix but, again, a deliberate design decision to make later if this is
ever observed in practice, not a wiring change.

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

from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID
from cora.api._capture_observer import ROLE_IMAGES_COLLECTED, ROLE_IMAGES_SAVED
from cora.api._capture_progress_feeder import CaptureProgressFeeder, capture_progress_flush_loop
from cora.infrastructure.logging import get_logger
from cora.run.aggregates.run.state import CaptureProgressSnapshot
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs.query import ListRuns
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.ports.capture_observer import (
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CapturePhase,
    CaptureProgressObservation,
)
from cora.shared.identity import MonitorSourceId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.infrastructure.config import Settings
    from cora.infrastructure.kernel import Kernel
    from cora.run.aggregates.run import FeedHeartbeatStore
    from cora.run.aggregates.run.state import Run
    from cora.run.features.append_observations.handler import Handler as AppendObservationsHandler
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.run.features.record_witnessed_run.handler import Handler as RecordWitnessedRunHandler
    from cora.run.features.record_witnessed_run_outcome.handler import (
        Handler as RecordWitnessedRunOutcomeHandler,
    )
    from cora.run.features.truncate_run.handler import Handler as TruncateRunHandler
    from cora.run.ports.capture_observer import CaptureObserver
    from cora.shared.identifier import Identifier

_RECONNECT_DELAY_SECONDS = 5.0
_CAPTURE_PROGRESS_DEFAULT_FLUSH_TICK_SECONDS = 10.0
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

_FLUSH_TRIGGER_PHASES = frozenset({CapturePhase.BEGUN, CapturePhase.ENDED, CapturePhase.ABORTED})
"""Phases where the recorder may close or replace a Run (slice 10).
`run_witness_loop` flushes a capture's buffered progress readings
BEFORE the recorder acts on one of these, so a reading already
BUFFERED at that instant is attributed to the Run it belongs to rather
than lost to a closed logbook or attached to the wrong Run after a
truncate-then-promote. This narrows the window; it does not close it:
`_capture_observer.py` runs a status/abort/images_saved/images_collected
pump per role, all feeding one unordered merge queue, and slice 9
already accepts that pump ordering is not structurally guaranteed, only
realistic CA delivery. A progress reading whose callback lands AFTER
this dispatch (rather than before) is either dropped
(`capture_progress.dropped_no_open_run`) or, on the rarer truncate-then-
promote path, attributed to the newly-promoted Run instead of the one
closing. Accepted residual, same severity class as the existing
status/abort ordering one: one row, not a trail, and 2-BM's TomoScan
only calls `update_status()` from its polling loop, so the progress
PVs do not move at `Beginning scan` time in practice -- a fact about
the deployed tool, not something this ordering enforces."""


def observe_capture(observation: CaptureLifecycleObservation) -> None:
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
        record_witnessed_run_outcome: RecordWitnessedRunOutcomeHandler,
        truncate_run: TruncateRunHandler,
        settings: Settings,
        open_captures: dict[str, UUID] | None = None,
    ) -> None:
        self._deps = deps
        self._record_witnessed_run = record_witnessed_run
        self._record_witnessed_run_outcome = record_witnessed_run_outcome
        self._truncate_run = truncate_run
        self._settings = settings
        self._open_captures: dict[str, UUID] = dict(open_captures or {})
        self._last_progress: dict[str, dict[str, CaptureProgressObservation]] = {}

    def open_captures(self) -> dict[str, UUID]:
        """A snapshot of every capture_code currently open, mapped to
        its run_id.

        Read-only accessor over the same dedup map `_promote` /
        `_truncate_stale` / `_record_outcome` mutate (populated from
        this process's own promotions, plus a prior process's via the
        boot-time `rebuild_open_captures`, which is itself scoped to
        `conduct_mode="Witnessed"` Runs only); `_open_captures` stays
        single-writer (this recorder). Slice 10's `CaptureProgressFeeder`
        is the consumer: it scopes every write it makes to a run_id this
        method names, never one sourced any other way, which is what
        keeps its `AppendObservations` grant (no `conduct_mode` gate)
        from being able to reach an operator-driven Run -- the same
        chain (this map, fed only by a Witnessed-filtered query) that
        already backstops `TruncateRun`'s equally ungated decider. See
        `cora.agent.seed_capture_progress_feeder` for the full security
        note. Returns a copy: the caller cannot mutate this recorder's
        own state through it.
        """
        return dict(self._open_captures)

    async def observe_capture(self, observation: CaptureLifecycleObservation) -> None:
        observe_capture(observation)
        if not self._settings.run_witness_recording_enabled:
            return

        phase = observation.phase

        if phase is CapturePhase.BEGUN:
            if observation.capture_code in self._open_captures:
                await self._truncate_stale(observation)
            await self._promote(observation)
        elif phase in _TERMINAL_PHASES:
            await self._record_outcome(observation)
        # PROGRESSING, UNRECOGNIZED, and a None phase make no status
        # claim this state machine acts on: no-op regardless of state.

    def observe_progress(self, observation: CaptureProgressObservation) -> None:
        """Retain the latest reading per (capture_code, role), so a
        terminal can carry the counts even though
        `CaptureProgressFeeder.flush_capture` pops its own buffer for
        the same code before `_record_outcome` builds the command
        (`run_witness_loop` flushes first; see that function's
        docstring). Synchronous and non-blocking, same contract as
        `CaptureProgressFeeder.offer`.

        Gated on `run_witness_recording_enabled`, same as
        `observe_capture`: shadow mode retains nothing because it
        writes nothing. Bounded by (capture codes x progress roles)
        from the deployment's own config, never by substrate rate, the
        same argument `CaptureProgressFeeder`'s own buffer makes.

        Deliberately NOT gated on `capture_progress_recording_enabled`.
        That flag's own docstring (`Settings`) scopes it to one thing:
        whether progress roles are buffered and written as
        `AppendObservations` rows against the promoted Run, the full
        per-tick trail. This retention is a different, cheaper feature:
        the last value per role, kept only to attach as evidence on the
        eventual terminal. A deployment can therefore get terminal
        evidence without paying for the full trail; the reverse
        (`capture_progress_recording_enabled=True` requiring
        `run_witness_recording_enabled=True`) is enforced at boot in
        `main.py`'s `_enforce_run_witness_recording_gate` for the
        unrelated reason that a trail write needs a promoted Run to
        write against.

        Eviction lives in `_promote`, `_truncate_stale`, and
        `_record_outcome`'s success path, alongside each one's existing
        `_open_captures` mutation, so retained progress never outlives
        the Run it was retained for.
        """
        if not self._settings.run_witness_recording_enabled:
            return
        by_role = self._last_progress.setdefault(observation.capture_code, {})
        by_role[observation.role] = observation

    async def _promote(self, observation: CaptureLifecycleObservation) -> None:
        # A prior capture's retained progress, if any, belongs to that
        # capture's own terminal, never to this one: clear before
        # promoting so a stale carry-over cannot ride onto the new
        # Run's eventual outcome.
        self._last_progress.pop(observation.capture_code, None)
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

    async def _truncate_stale(self, observation: CaptureLifecycleObservation) -> None:
        code = observation.capture_code
        # Pop unconditionally, before attempting the truncate: the new
        # capture promotes regardless of whether the stale Run could be
        # closed, so the dedup state must already read IDLE by the time
        # `_promote` runs next in `observe_capture`.
        #
        # SECURITY NOTE (see seed_run_witness.py): TruncateRun's decider
        # has no conduct_mode gate, unlike RecordWitnessedRunOutcome's.
        # This principal's safety depends entirely on `stale_run_id`
        # coming from `_open_captures`, which this runtime populates
        # exclusively from its own promotions. Never source a run_id
        # for this call from anywhere else (substrate input, a
        # capture_code-derived guess, etc.).
        stale_run_id = self._open_captures.pop(code, None)
        # The stale Run's retained progress dies with it, same
        # unconditional-before-the-call posture as `_open_captures`
        # above: whatever this code's next BEGUN promotes is a
        # different capture and must not inherit counts that describe
        # the one being truncated.
        self._last_progress.pop(code, None)
        if stale_run_id is None:
            return

        try:
            await self._truncate_run(
                TruncateRun(
                    run_id=stale_run_id,
                    reason=(
                        f"RunWitness observed a new Begun for capture {code} "
                        f"while the previous Run was still open: the terminal "
                        f"for that capture was never observed."
                    ),
                    interrupted_at=None,
                ),
                principal_id=RUN_WITNESS_AGENT_ID,
                correlation_id=self._deps.id_generator.new_id(),
            )
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            _log.warning(
                "run_witness.truncate_unauthorized",
                capture_code=code,
                run_id=str(stale_run_id),
            )
        except Exception:
            _log.exception(
                "run_witness.truncate_failed",
                capture_code=code,
                run_id=str(stale_run_id),
            )
        else:
            _log.info(
                "run_witness.truncated_stale_run",
                capture_code=code,
                run_id=str(stale_run_id),
            )

    async def _record_outcome(self, observation: CaptureLifecycleObservation) -> None:
        phase = observation.phase
        if phase is not CapturePhase.ENDED and phase is not CapturePhase.ABORTED:
            # Defensive: observe_capture only calls this method for a
            # terminal phase, but re-checking here (rather than trusting
            # the caller) also narrows `phase` from `CapturePhase | None`
            # for the RecordWitnessedRunOutcome construction below.
            return
        code = observation.capture_code
        run_id = self._open_captures.get(code)
        if run_id is None:
            return

        command = RecordWitnessedRunOutcome(
            run_id=run_id,
            capture_code=code,
            observed_phase=phase,
            observed_at=observation.observed_at,
            monitor_source_id=RUN_WITNESS_MONITOR_SOURCE_ID,
            trigger="Monitor",
            capture_progress_snapshot=self._build_progress_snapshot(code),
        )
        try:
            await self._record_witnessed_run_outcome(
                command,
                principal_id=RUN_WITNESS_AGENT_ID,
                correlation_id=self._deps.id_generator.new_id(),
            )
        except asyncio.CancelledError:
            raise
        except UnauthorizedError:
            # Configuration fault: the RunWitness principal is not
            # granted RecordWitnessedRunOutcome. Log loudly; leave the
            # entry open so the next BEGUN truncates it and promotes
            # fresh once the grant is fixed.
            _log.warning(
                "run_witness.outcome_unauthorized",
                capture_code=code,
                run_id=str(run_id),
            )
            return
        except Exception:
            _log.exception(
                "run_witness.outcome_failed",
                capture_code=code,
                run_id=str(run_id),
            )
            return
        self._open_captures.pop(code, None)
        # Success path only, mirroring `_open_captures` immediately
        # above: on failure both dicts stay populated so the next
        # BEGUN's truncate-then-promote clears them together, keeping
        # the two eviction states in lockstep.
        self._last_progress.pop(code, None)
        _log.info(
            "run_witness.outcome_recorded",
            capture_code=code,
            run_id=str(run_id),
            observed_phase=str(observation.phase),
        )

    def _build_progress_snapshot(self, code: str) -> CaptureProgressSnapshot | None:
        """The evidence a witnessed terminal carries for `code`: the
        last `collected` / `saved` progress readings `observe_progress`
        retained, or `None` if nothing was retained for either role.

        Whole object `None`, never all-`None` fields: absence must read
        as "no progress reading reached CORA before this terminal",
        distinct from "readings arrived and reported zero images". See
        `CaptureProgressSnapshot`'s own docstring for why these counts
        carry no completeness judgment.
        """
        # Role keys are `_capture_observer.py`'s `ROLE_IMAGES_COLLECTED` /
        # `ROLE_IMAGES_SAVED` (imported, not re-literaled here), the
        # config-facing vocabulary; `CaptureProgressSnapshot`'s field
        # names are the facility-neutral `collected` / `saved` pair,
        # deliberately not the same strings (see that VO's own
        # docstring).
        by_role = self._last_progress.get(code, {})
        collected = by_role.get(ROLE_IMAGES_COLLECTED)
        saved = by_role.get(ROLE_IMAGES_SAVED)
        if collected is None and saved is None:
            return None
        collected_count, collected_total, collected_at = _progress_fields(collected)
        saved_count, saved_total, saved_at = _progress_fields(saved)
        return CaptureProgressSnapshot(
            collected_count=collected_count,
            collected_total=collected_total,
            collected_at=collected_at,
            saved_count=saved_count,
            saved_total=saved_total,
            saved_at=saved_at,
        )


def _progress_fields(
    observation: CaptureProgressObservation | None,
) -> tuple[float | None, float | None, datetime | None]:
    """`(value, commanded_total, observed_at)` for one retained role
    reading, or `(None, None, None)` when nothing was retained for it.
    Factored out of `_build_progress_snapshot` so its two roles share
    one conversion instead of six near-identical guarded expressions."""
    if observation is None:
        return None, None, None
    return observation.value, observation.commanded_total, observation.observed_at


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
    feeder: CaptureProgressFeeder | None = None,
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, logging (and, with a recorder, promoting)
    each observation; re-subscribe on stream end.

    A `CaptureProgressObservation` fans out to TWO independent sinks:
    `recorder.observe_progress()` (retains the latest per-role reading
    so a terminal can carry it as evidence; see `RunWitnessRecorder
    ._build_progress_snapshot`) and `feeder.offer()` (buffers it for
    the next `AppendObservations` flush). Order between the two is
    immaterial: both are synchronous and neither raises in normal
    operation. A `CaptureLifecycleObservation` on a phase in
    `_FLUSH_TRIGGER_PHASES` triggers `feeder.flush_capture()` BEFORE the
    recorder acts on it, so a capture's buffered progress trail is
    attributed to its Run before that Run can close or be replaced;
    this ordering is unchanged by the fan-out above; `recorder
    .observe_progress` retains independently of the flush and is not
    itself flushed. `feeder=None` (recording off, or
    `capture_progress_recording_enabled=False`) and `recorder=None`
    each make their own branch a no-op independently.
    """
    if not capture_codes:
        return
    scope = CaptureObserverScope(capture_codes=capture_codes)
    while True:
        try:
            async for observation in observer.observe(scope):
                if isinstance(observation, CaptureProgressObservation):
                    if recorder is not None:
                        recorder.observe_progress(observation)
                    if feeder is not None:
                        feeder.offer(observation)
                    continue
                if feeder is not None and observation.phase in _FLUSH_TRIGGER_PHASES:
                    try:
                        await feeder.flush_capture(observation.capture_code)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        _log.exception(
                            "run_witness.progress_flush_failed",
                            capture_code=observation.capture_code,
                        )
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
    record_witnessed_run_outcome: RecordWitnessedRunOutcomeHandler | None = None,
    truncate_run: TruncateRunHandler | None = None,
    open_captures: dict[str, UUID] | None = None,
    append_observations: AppendObservationsHandler | None = None,
    feed_heartbeat_store: FeedHeartbeatStore | None = None,
    capture_progress_recording_enabled: bool = False,
    capture_progress_flush_tick_seconds: float = _CAPTURE_PROGRESS_DEFAULT_FLUSH_TICK_SECONDS,
) -> AsyncGenerator[None]:
    """Run the watcher as a background task for the app's lifetime.

    No-op when `capture_codes` is empty: yields immediately without
    starting a task, mirroring `enclosure_permit_monitor_lifespan`'s
    no-op-when-unconfigured shape.

    `deps` stays optional (unlike the sibling `run_supervisor_lifespan`
    / `run_initiator_lifespan`, which require it) so every existing
    shadow-only caller needs no change: recording is the only thing that
    needs a Kernel (for id generation), so `deps`, `record_witnessed_run_outcome`,
    and `truncate_run` are only required when `record_witnessed_run` is
    also supplied. All three: a recorder that could promote but not
    terminate would reintroduce the exact wedge (a witnessed Run stuck
    in `Running` forever) this slice exists to close.

    `capture_progress_recording_enabled=True` (slice 10) additionally
    requires `record_witnessed_run`, `append_observations`, and
    `feed_heartbeat_store`: a `CaptureProgressFeeder` writes progress
    readings against a Run only the recorder can name, so it cannot
    exist without one. Runs a second background task,
    `capture_progress_flush_loop`, alongside the drain loop.
    """
    if not capture_codes:
        yield
        return
    if record_witnessed_run is not None:
        missing = [
            name
            for name, value in (
                ("deps", deps),
                ("record_witnessed_run_outcome", record_witnessed_run_outcome),
                ("truncate_run", truncate_run),
            )
            if value is None
        ]
        if missing:
            msg = f"run_witness_lifespan: record_witnessed_run requires {', '.join(missing)}"
            raise ValueError(msg)

    recorder: RunWitnessRecorder | None = None
    if record_witnessed_run is not None:
        # Narrowed by the check above.
        assert deps is not None
        assert record_witnessed_run_outcome is not None
        assert truncate_run is not None
        recorder = RunWitnessRecorder(
            deps=deps,
            record_witnessed_run=record_witnessed_run,
            record_witnessed_run_outcome=record_witnessed_run_outcome,
            truncate_run=truncate_run,
            settings=deps.settings,
            open_captures=open_captures,
        )

    feeder: CaptureProgressFeeder | None = None
    if capture_progress_recording_enabled:
        missing = [
            name
            for name, value in (
                ("record_witnessed_run", record_witnessed_run),
                ("append_observations", append_observations),
                ("feed_heartbeat_store", feed_heartbeat_store),
            )
            if value is None
        ]
        if missing:
            msg = (
                "run_witness_lifespan: capture_progress_recording_enabled "
                f"requires {', '.join(missing)}"
            )
            raise ValueError(msg)
        # Narrowed by the checks above: record_witnessed_run is not None
        # here, so the recorder-building block above already ran and
        # deps is not None either.
        assert deps is not None
        assert recorder is not None
        assert append_observations is not None
        assert feed_heartbeat_store is not None
        if not deps.settings.run_witness_recording_enabled:
            # Defensive, mirrors `_promote`'s own capture_watch_plan_id
            # check: `_enforce_run_witness_recording_gate` (main.py)
            # already refuses to boot in this state, but a direct
            # in-process caller that sets this flag without also
            # enabling run_witness_recording_enabled would otherwise get
            # a feeder that writes REAL rows while the recorder is still
            # shadow-only (writes nothing). Refuse rather than silently
            # break shadow mode's own promise.
            msg = (
                "run_witness_lifespan: capture_progress_recording_enabled=True "
                "requires deps.settings.run_witness_recording_enabled=True"
            )
            raise ValueError(msg)
        feeder = CaptureProgressFeeder(
            deps=deps,
            append_observations=append_observations,
            feed_heartbeat_store=feed_heartbeat_store,
            open_captures=recorder.open_captures,
            principal_id=CAPTURE_PROGRESS_FEEDER_AGENT_ID,
        )

    tasks = [
        asyncio.create_task(
            run_witness_loop(
                observer=observer,
                capture_codes=capture_codes,
                recorder=recorder,
                feeder=feeder,
            ),
            name="run-witness",
        )
    ]
    if feeder is not None:
        tasks.append(
            asyncio.create_task(
                capture_progress_flush_loop(
                    feeder, interval_seconds=capture_progress_flush_tick_seconds
                ),
                name="capture-progress-flush",
            )
        )
    try:
        yield
    finally:
        # Cancel + await both tasks BEFORE the final flush below: this
        # guarantees the periodic flush loop is no longer running (so
        # it cannot race the final flush for the same capture_code) and
        # that `_flush_lock` is free (an `async with` block releases a
        # lock on cancellation same as on any other exit).
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if feeder is not None:
            # Best-effort: whatever is still buffered at shutdown is the
            # highest-water-mark reading per channel (the buffer is
            # latest-wins), so losing it silently would discard the
            # single most informative row. Never let this raise past
            # lifespan teardown.
            with contextlib.suppress(Exception):
                await feeder.flush()


__all__ = [
    "RUN_WITNESS_MONITOR_SOURCE_ID",
    "RunWitnessRecorder",
    "observe_capture",
    "rebuild_open_captures",
    "run_witness_lifespan",
    "run_witness_loop",
]
