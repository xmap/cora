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

## Coverage trail (slice 16), independent of the recording switch

Every observation reaching `RunWitnessRecorder.observe_capture` also
writes one `CaptureProbe` row (see `cora.run.aggregates.run.capture_probes`
for the full design argument), gated on its OWN kill switch,
`Settings.capture_probe_recording_enabled` -- NOT on
`run_witness_recording_enabled`. This is deliberate: the trail's value
is realized specifically while recording is off, since it scopes on
`capture_code` rather than a promoted Run's id. The write happens
BEFORE the `run_witness_recording_enabled` early-return below, mirrors
`enclosure._monitor.record_observation`'s failure posture exactly (skip
with a log line while `deps.schema_posture == "degraded"`; otherwise
catch, log, and continue on any other exception -- never raise into the
drain loop), and never suppresses the log line above it or the
promotion/termination logic below it.

## Promotion and termination (when run_witness_recording_enabled is True)

Per capture_code, a small dedup state machine:

  - `BEGUN` while no Run is open for this code: call `record_witnessed_run`
    and, on success, remember the returned run_id as OPEN. On failure
    (any raised error, including an authorization misconfiguration),
    log and stay unopened so the next `BEGUN` retries. On success, also
    call the configured `CaptureBaselineReader` (slice 12) exactly once
    to snapshot the genesis-baseline PVs against the new Run; a failure
    there is logged and never unwinds the promotion that already
    committed (see `RunWitnessRecorder._read_baseline`). Also calls the
    configured `CaptureExperimentIdentityReader` (slice 14a) exactly once, same
    posture, to vault the proposal / ESAF / ESAF-DOI PVs against the new
    Run (see `RunWitnessRecorder._read_experiment_identity`). Before the
    `RecordWitnessedRun` command is even built, consumes the retained
    `orchestrator_ref` reading for this code (if any) through the
    consume-once staleness guard, so the promoted Run's genesis can
    carry an external orchestrator's own run identifier as a second
    `external_refs` entry (see "Orchestrator-ref pairing" below).
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

## Capture path pairing (slice 13)

Closes the "which file did this Run produce" findability gap (auto-
correlation stays deferred; this only makes the manual pairing
possible). Source is the areaDetector file plugin's own filename
readback (`full_file_name` role, `_capture_observer.py`), NOT
tomoscan's own `FullFileName`: upstream `tomoscan.py`'s `end_scan()`
writes `ScanStatus='Scan complete'` (CORA's terminal) FOUR statements
BEFORE it writes `FullFileName`, so a synchronous read at the terminal
against that PV would return the PREVIOUS scan's filename. The
areaDetector PV is written at file OPEN, i.e. before the terminal, so
it does not have this race -- but "written before the terminal" is not
by itself sufficient: the file plugin also fires independently of any
one capture, so a value retained from a PREVIOUS capture (or a
reconnect redelivering one) could still be sitting in
`_last_capture_path` when THIS capture's terminal arrives.

The guard: `_promote` records the BEGUN observation's OWN substrate
time into `_begun_at[code]` (never CORA's clock -- comparing two
substrate timestamps from the same control system avoids a
CORA-host-vs-IOC clock-skew question this guard does not need to
answer). At the terminal, `_resolve_capture_path` accepts the retained
reading only if its `observed_at` is at or after that value. This is
the freshness guard the "CA's redeliver-on-resubscribe" residual above
names as a real fix "if this is ever observed in practice" for
progress readings -- implemented here, scoped to this one role, because
Finding A makes it load-bearing rather than optional: without it, this
feature would silently pair Runs with the WRONG file on every
reconnect-during-BEGUN window, not just degrade one row's ordering.

`observed_path` is personal data (2-BM's directory layout embeds a
surname and a proposal number,`tomoscan_2bm.py:474-477`), so it is
never written to `RunCompleted` / `RunAborted` or any other event: it
goes to the `run_capture_path` PII vault (`CapturePathStore`,
mirroring `actor_profile` / `ProfileStore`) via `_write_capture_path`,
called at the end of `_record_outcome`'s success branch -- the outcome
has already committed by then, so (mirroring `_read_baseline`'s exact
posture) a vault-write failure is logged and never unwinds it. Gated
on the fifth kill switch, `capture_path_recording_enabled`. No log
line in this section ever includes `observed_path` itself; only
`capture_code` / `run_id` / lengths.

## Orchestrator-ref pairing

Joins a witnessed Run to an external orchestrator's own run identifier
for the same capture (e.g. a Bluesky RunEngine start-document uid),
carried as a second `external_refs` entry on `RunStarted` alongside
`capture-code`. Closes the "which Bluesky run produced this CORA Run"
findability gap the same way slice 13 closes the file-identity one;
CORA still never talks to the orchestrator directly, it only reads
whatever run identifier the orchestrator wrote to the substrate before
triggering the act `CaptureObserver` watches.

The ordering is the INVERSE of the capture-path guard above: a run uid
is written BEFORE the capture it names begins, never after, so there
is no "did the file open before or after BEGUN" question here -- the
question is "did this retained uid lead the current BEGUN by a
plausible amount, or is it a stale leftover from some earlier capture
whose BEGUN this recorder never saw close it out."

The guard, in `_consume_orchestrator_ref`: a retained reading is
CONSUMED (popped, never merely read) the moment a `BEGUN` for its
capture code is promoted, whether or not the reading passes the
checks below -- the structural fix, not a heuristic. A reading that
fails a check is simply gone; it cannot be reused by a LATER capture
the way a bug in a peek-without-pop implementation would allow. Then,
only if consumption returned something:

  - `observed_at` must be present on both the retained reading and
    the current BEGUN. Either missing means there is no substrate time
    to compare, so the guard fails closed (mirrors `_resolve_capture_
    path`'s identical posture when `_begun_at` has no entry).
  - The lead (`begun_at - observed_at`) must be non-negative: a
    negative lead means the uid reading's own substrate timestamp is
    AFTER this BEGUN's, which should not happen if the orchestrator
    writes its uid first, and signals either substrate clock skew
    between two channels or the two pumps having delivered out of
    their causal order (see the residual below).
  - The lead must not exceed `capture_orchestrator_ref_max_lead_
    seconds` (deployment-declared, not hardcoded): a uid retained far
    longer than a real orchestrator-to-BEGUN gap is more likely a
    stale leftover from a capture whose own BEGUN this recorder never
    promoted (a reconnect, or a non-orchestrator-driven scan that
    started while the substrate still held the previous run's uid)
    than genuine evidence for the current one.
  - The `(scheme, value)` pair must construct a valid `Identifier`:
    `Identifier.__post_init__` bounds both fields' length and rejects
    empty/whitespace-only text, the same validation `capture-code`
    itself is subject to.

Gated on the TENTH kill switch, `capture_orchestrator_ref_recording_enabled`,
independently of `run_witness_recording_enabled`'s sibling switches for
the personal-data-adjacent roles: unlike an observed capture path, a
run uid is not personal data, but it IS a second identity a facility
may want to withhold from the record independently of witnessing
itself (e.g. while `tomo-bits`' own plan is still being validated
against production). Retention (`observe_orchestrator_ref`) is gated
only on `run_witness_recording_enabled`, matching
`observe_capture_path`'s declare-vs-record split, so flipping the
tenth switch later does not miss whatever was already retained.

### Accepted residual: a stray scan inside the lead-time window can inherit a stale ref

The lead-time bound above narrows the exposure but does not close it:
if the orchestrator writes a uid, its own process is killed before it
clears the PV (a `finally` never runs), and a DIFFERENT tool starts a
real scan on the SAME capture code within the configured lead-time
window, this recorder cannot tell the two apart -- it attaches the
stale-but-recent uid to a Run the orchestrator never actually drove.
Same severity class as the reconnect-during-BEGUN residual above (a
data-quality degradation: one Run carries a ref that does not
describe it, never a corrupted attribution to a DIFFERENT Run's
event stream), and the same posture: no narrower signal is
implemented here; revisit if this is ever observed in practice.

### Accepted residual: the orchestrator-ref and status pumps have no enforced ordering

Mirrors the accepted `status`/`abort` pump-ordering residual above
exactly, for the same structural reason (`_capture_observer.py` runs
one pump per role, all feeding one unordered merge queue): if a
reconnect or an adversarial delivery pattern lets a capture's own
`BEGUN` reading reach this recorder BEFORE its paired
`orchestrator_ref` reading (despite the orchestrator having
written the uid to the substrate first), `_promote` finds nothing
retained and the Run promotes with no orchestrator ref at all -- never
a wrong one. The uid reading, arriving moments later, is then retained
for whatever capture comes NEXT, which is exactly the stale-leftover
shape the lead-time bound above exists to catch on that next
promotion.

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

from cora.agent.seed_capture_baseline_reader import CAPTURE_BASELINE_READER_AGENT_ID
from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
from cora.agent.seed_run_witness import RUN_WITNESS_AGENT_ID
from cora.api._capture_baseline_reader import CaptureBaselineReader
from cora.api._capture_experiment_identity_reader import CaptureExperimentIdentityReader
from cora.api._capture_observer import ROLE_IMAGES_COLLECTED, ROLE_IMAGES_SAVED
from cora.api._capture_progress_feeder import CaptureProgressFeeder, capture_progress_flush_loop
from cora.data.adapters.capture_path_locator import active_scan_transport
from cora.infrastructure.logging import get_logger
from cora.run.aggregates.run.capture_probes import CaptureProbe
from cora.run.aggregates.run.state import (
    CapturePreconditionBypassSnapshot,
    CaptureProgressSnapshot,
    extract_capture_code,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs.query import ListRuns
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run_outcome.command import RecordWitnessedRunOutcome
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.ports.capture_observer import (
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CaptureOrchestratorRefObservation,
    CapturePathObservation,
    CapturePhase,
    CapturePreconditionBypassObservation,
    CaptureProgressObservation,
)
from cora.shared.identifier import Identifier, InvalidIdentifierError
from cora.shared.identity import MonitorSourceId
from cora.shared.storage_root import matched_storage_root

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping
    from datetime import datetime

    from cora.infrastructure.config import Settings
    from cora.infrastructure.kernel import Kernel
    from cora.operation.ports.control_port import ControlPort
    from cora.run.aggregates.run import (
        CapturePathStore,
        CaptureProbeStore,
        ExperimentIdentityStore,
        FeedHeartbeatStore,
    )
    from cora.run.aggregates.run.state import Run
    from cora.run.features.append_observations.handler import Handler as AppendObservationsHandler
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.run.features.record_witnessed_run.handler import Handler as RecordWitnessedRunHandler
    from cora.run.features.record_witnessed_run_outcome.handler import (
        Handler as RecordWitnessedRunOutcomeHandler,
    )
    from cora.run.features.truncate_run.handler import Handler as TruncateRunHandler
    from cora.run.ports.capture_observer import CaptureObserver

_RECONNECT_DELAY_SECONDS = 5.0
_CAPTURE_PROGRESS_DEFAULT_FLUSH_TICK_SECONDS = 10.0
_PAGE_LIMIT = 100

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
        baseline_reader: CaptureBaselineReader | None = None,
        capture_path_store: CapturePathStore | None = None,
        experiment_identity_reader: CaptureExperimentIdentityReader | None = None,
        capture_probe_store: CaptureProbeStore | None = None,
    ) -> None:
        self._deps = deps
        self._record_witnessed_run = record_witnessed_run
        self._record_witnessed_run_outcome = record_witnessed_run_outcome
        self._truncate_run = truncate_run
        self._settings = settings
        self._open_captures: dict[str, UUID] = dict(open_captures or {})
        self._last_progress: dict[str, dict[str, CaptureProgressObservation]] = {}
        self._last_precondition_bypass: dict[str, CapturePreconditionBypassObservation] = {}
        self._baseline_reader = baseline_reader
        self._capture_path_store = capture_path_store
        self._experiment_identity_reader = experiment_identity_reader
        self._capture_probe_store = capture_probe_store
        self._last_capture_path: dict[str, CapturePathObservation] = {}
        """Slice 13: the latest `full_file_name` reading retained per
        capture_code, mirroring `_last_progress`'s retain-latest shape.
        Evicted in lockstep with `_begun_at` below in `_promote` /
        `_truncate_stale` / `_record_outcome`'s success path."""
        self._last_orchestrator_ref: dict[str, CaptureOrchestratorRefObservation] = {}
        """The latest `orchestrator_ref` reading retained per
        capture_code, mirroring `_last_capture_path`'s retain-latest
        shape. UNLIKE every other retained dict on this recorder,
        consumption is a POP, not a lookup: `_consume_orchestrator_ref`
        (called from `_promote`) always removes the entry for the code
        being promoted, whether or not the reading passes its guard,
        so a rejected reading can never be reused by a later capture.
        See this module's "Orchestrator-ref pairing" docstring
        section."""
        self._begun_at: dict[str, datetime] = {}
        """Slice 13: the BEGUN observation's OWN substrate time per
        capture_code, recorded in `_promote`. The dual-clock guard in
        `_resolve_capture_path` compares a retained
        `CapturePathObservation.observed_at` against this value, never
        against CORA's own clock (see this module's "Capture path
        pairing" docstring section)."""

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

    def progress_readings(self) -> dict[UUID, dict[str, CaptureProgressObservation]]:
        """A snapshot of the latest progress reading per role, keyed by
        run_id, for every currently-open capture.

        Read-only view combining `open_captures` (capture_code -> run_id)
        with `_last_progress` (capture_code -> role -> reading) so a
        caller outside this recorder (a live status view is the intended
        consumer) never needs to know capture_code exists. A capture with
        no progress reading yet is simply absent from the result, not an
        empty dict. Returns copies of both the outer mapping and each
        inner one: the caller cannot mutate this recorder's own state
        through it, same posture as `open_captures`.

        This is the ONLY place these readings are available at substrate
        rate: `entries_run_observations` (the Postgres-durable path) is
        capped at `capture_progress_flush_tick_seconds` and never carries
        `commanded_total` at all (dropped at the `ObservationInput`
        boundary), so a consumer wanting the "N of M" figure has no
        substitute for reading this recorder directly.
        """
        result: dict[UUID, dict[str, CaptureProgressObservation]] = {}
        for capture_code, run_id in self._open_captures.items():
            readings = self._last_progress.get(capture_code)
            if readings:
                result[run_id] = dict(readings)
        return result

    async def observe_capture(self, observation: CaptureLifecycleObservation) -> None:
        observe_capture(observation)
        await self._write_capture_probe(observation)
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

    async def _write_capture_probe(self, observation: CaptureLifecycleObservation) -> None:
        """Record one `CaptureProbe` row for `observation` (slice 16).

        Gated on its OWN kill switch, `capture_probe_recording_enabled`,
        independent of `run_witness_recording_enabled` -- see this
        module's docstring, "Coverage trail". No-op when
        `_capture_probe_store` is `None` (mirrors every other optional
        store on this recorder) or the switch is off.

        Mirrors `enclosure._monitor.record_observation`'s failure
        posture exactly: no probe row at all while
        `deps.schema_posture == "degraded"` (a probe row asserting reach
        during a window CORA cannot actually record anything would be
        worse than the gap it would paper over), otherwise a try/except
        around the write that logs and continues on any exception other
        than cancellation. A bookkeeping write must never suppress the
        log line above it or the promotion/termination logic below it.
        """
        if self._capture_probe_store is None or not self._settings.capture_probe_recording_enabled:
            return
        if self._deps.schema_posture == "degraded":
            _log.warning(
                "run_witness.capture_probe_skipped_degraded_schema",
                capture_code=observation.capture_code,
            )
            return
        try:
            await self._capture_probe_store.append(
                [
                    CaptureProbe(
                        event_id=self._deps.id_generator.new_id(),
                        capture_code=observation.capture_code,
                        source_kind=observation.source_kind,
                        source_id=observation.source_id,
                        reach_tier=observation.reach_tier,
                        phase_claimed=observation.phase is not None,
                        observed_at=observation.observed_at,
                    )
                ]
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # `_log.exception` (rather than `_write_capture_path`'s
            # `_log.error`-plus-class-name-only posture, see that
            # method's own comment) is safe here: every column on this
            # row -- capture_code, source_kind, source_id, reach_tier,
            # phase_claimed -- is an instrument identifier, never
            # personal data, so a CHECK-violation's asyncpg `DETAIL:`
            # line carrying the row's own values discloses nothing this
            # log sink would need to erase.
            _log.exception(
                "run_witness.capture_probe_write_failed",
                capture_code=observation.capture_code,
            )

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

    def observe_precondition_bypass(
        self, observation: CapturePreconditionBypassObservation
    ) -> None:
        """Retain the latest `testing`-role reading per capture_code, so
        the NEXT `BEGUN` for this code can stamp it onto the witnessed
        genesis (see `_promote` / `_build_precondition_bypass_snapshot`).

        Gated on `run_witness_recording_enabled`, same as
        `observe_progress`: shadow mode retains nothing because it
        writes nothing.

        Deliberately NEVER evicted, unlike `_last_progress`: the
        `testing` role is a substrate-level flag an operator sets
        independent of any one capture (TomoScan does not reset it
        between scans), so the reading retained across a capture
        boundary is not stale evidence about the WRONG capture the way
        a leftover progress count would be. It stays the honest answer
        to "what did `testing` last read" until a fresh reading
        replaces it, however long ago that was; `observed_at` is what
        lets a reader judge that gap at genesis time, not eviction.
        """
        if not self._settings.run_witness_recording_enabled:
            return
        self._last_precondition_bypass[observation.capture_code] = observation

    def _build_precondition_bypass_snapshot(
        self, code: str
    ) -> CapturePreconditionBypassSnapshot | None:
        """The evidence a witnessed genesis carries for `code`: the last
        `testing` reading `observe_precondition_bypass` retained, or
        `None` if none has ever arrived (no `testing` role declared for
        this code, or the substrate has not reported one yet).
        """
        observation = self._last_precondition_bypass.get(code)
        if observation is None:
            return None
        return CapturePreconditionBypassSnapshot(
            beam_preconditions_bypassed=observation.beam_preconditions_bypassed,
            observed_at=observation.observed_at,
        )

    def observe_capture_path(self, observation: CapturePathObservation) -> None:
        """Retain the latest `full_file_name`-role reading per
        capture_code (slice 13), so a terminal can resolve it through
        `_resolve_capture_path`.

        Gated on `run_witness_recording_enabled`, same as
        `observe_progress`: shadow mode retains nothing because it
        writes nothing.

        Evicted WITH `_begun_at`, unlike `_last_precondition_bypass`:
        `full_file_name` describes one specific capture's output file,
        so a reading retained across a capture boundary IS stale
        evidence about the wrong capture, the same reasoning
        `_last_progress` already applies. See `_promote` /
        `_truncate_stale` / `_record_outcome`'s success path.

        Note this method does NOT itself apply the dual-clock guard: it
        retains whatever arrives, latest-wins, exactly like
        `observe_progress`. The guard is `_resolve_capture_path`'s job,
        applied once, at the terminal -- not here, on every reading.
        """
        if not self._settings.run_witness_recording_enabled:
            return
        self._last_capture_path[observation.capture_code] = observation

    def _resolve_capture_path(self, code: str) -> tuple[str, datetime] | None:
        """The dual-clock guard (Finding A, slice 13): a retained
        `full_file_name` reading is usable for `code`'s terminal only if
        its OWN substrate time is at or after this code's own BEGUN
        substrate time. Returns `(observed_path, observed_at)` when the
        guard passes, `None` when there is nothing retained, `code` was
        never promoted with a substrate time to compare against
        (`_begun_at` has no entry), or the retained reading predates it.

        `None` is a legitimate, expected outcome (never observed yet,
        or correctly rejected as belonging to a previous capture), not
        an error; callers must not log it as one.
        """
        observation = self._last_capture_path.get(code)
        begun_at = self._begun_at.get(code)
        if observation is None or begun_at is None:
            return None
        if observation.observed_at is None or observation.observed_at < begun_at:
            return None
        return observation.observed_path, observation.observed_at

    def observe_orchestrator_ref(self, observation: CaptureOrchestratorRefObservation) -> None:
        """Retain the latest `orchestrator_ref` reading per
        capture_code, so the NEXT `BEGUN` for this code can attach it to
        the witnessed genesis as a second `external_refs` entry (see
        `_promote` / `_consume_orchestrator_ref`).

        Gated on `run_witness_recording_enabled` only, same as
        `observe_capture_path`: retention is cheap and reversible; the
        actual attachment onto `RunStarted` is separately gated on the
        TENTH kill switch, `capture_orchestrator_ref_recording_enabled`,
        inside `_promote`, mirroring `capture_path_recording_enabled`'s
        declare-vs-record split.

        Evicted WITH `_begun_at`, unlike `_last_precondition_bypass`: a
        run uid names one specific capture, so a reading retained
        across a capture boundary IS stale evidence about the wrong
        capture, the same reasoning `_last_capture_path` applies.
        UNCONDITIONALLY consumed (popped, not merely read) by
        `_consume_orchestrator_ref` at the next `BEGUN`, whether or not
        it is ultimately attached, so a rejected reading cannot be
        reused by a capture after that. See this module's
        "Orchestrator-ref pairing" docstring section.
        """
        if not self._settings.run_witness_recording_enabled:
            return
        self._last_orchestrator_ref[observation.capture_code] = observation

    def _consume_orchestrator_ref(self, code: str, begun_at: datetime | None) -> Identifier | None:
        """Pop and validate the retained `orchestrator_ref` reading
        for `code`, applying the lead-time guard (see "Orchestrator-ref
        pairing" above). ALWAYS pops, whether the guard passes or not:
        a rejected reading must not survive to be reused by a LATER
        promotion -- the structural fix this module's docstring
        describes, not a heuristic.

        `begun_at` is the CURRENT BEGUN's own substrate time (already
        recorded into `self._begun_at[code]` by the caller before this
        runs), never CORA's clock, mirroring `_resolve_capture_path`'s
        identical choice to compare two substrate timestamps rather
        than involve a CORA-host-vs-IOC clock-skew question this guard
        does not need to answer.

        Returns `None` on any rejection (nothing retained, no
        reference time to compare against, a negative or over-bound
        lead, or a malformed `(scheme, value)` pair); every rejection
        branch logs its own reason. `None` is a legitimate, expected
        outcome on most captures (no orchestrator involved at all), so
        the caller must not treat it as an error, only as "no ref to
        attach."
        """
        observation = self._last_orchestrator_ref.pop(code, None)
        if observation is None:
            return None
        if begun_at is None or observation.observed_at is None:
            _log.warning(
                "run_witness.orchestrator_ref_rejected_no_reference_time",
                capture_code=code,
            )
            return None
        lead_seconds = (begun_at - observation.observed_at).total_seconds()
        if lead_seconds < 0:
            _log.warning(
                "run_witness.orchestrator_ref_rejected_reordered",
                capture_code=code,
                lead_seconds=lead_seconds,
            )
            return None
        if lead_seconds > self._settings.capture_orchestrator_ref_max_lead_seconds:
            _log.warning(
                "run_witness.orchestrator_ref_rejected_stale",
                capture_code=code,
                lead_seconds=lead_seconds,
            )
            return None
        try:
            return Identifier(scheme=observation.scheme, value=observation.value)
        except InvalidIdentifierError:
            _log.warning(
                "run_witness.orchestrator_ref_rejected_malformed",
                capture_code=code,
            )
            return None

    async def _promote(self, observation: CaptureLifecycleObservation) -> None:
        # A prior capture's retained progress, if any, belongs to that
        # capture's own terminal, never to this one: clear before
        # promoting so a stale carry-over cannot ride onto the new
        # Run's eventual outcome.
        self._last_progress.pop(observation.capture_code, None)
        # Slice 13: same reasoning for a retained full_file_name
        # reading -- it describes the PREVIOUS capture's file, not this
        # one's, until a fresh reading arrives.
        self._last_capture_path.pop(observation.capture_code, None)
        if observation.observed_at is not None:
            # The dual-clock guard's reference point: recorded here,
            # from this BEGUN's OWN substrate time, never CORA's clock.
            self._begun_at[observation.capture_code] = observation.observed_at
        else:
            # No substrate time on this BEGUN means the guard has
            # nothing to compare against; a stale prior entry must not
            # be left standing to be compared against the WRONG
            # promotion (see `_resolve_capture_path`).
            self._begun_at.pop(observation.capture_code, None)
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

        # Always consume (pop) whatever is retained, whether or not the
        # TENTH kill switch is on: an orchestrator ref left unconsumed
        # while the switch is off would otherwise carry over, stale,
        # to whatever capture is open once the switch flips on. Only
        # USE the result when the switch is on. See "Orchestrator-ref
        # pairing" above. Passed directly rather than re-read via
        # `self._begun_at.get(...)`: the block above just set that
        # entry FROM this same `observation.observed_at` (or cleared it
        # when `observation.observed_at is None`), so the two are
        # always equal here -- reading back through the dict would only
        # add a hidden ordering dependency on the block above running
        # first, for no behavioral difference.
        consumed_orchestrator_ref = self._consume_orchestrator_ref(
            observation.capture_code, observation.observed_at
        )
        orchestrator_ref = (
            consumed_orchestrator_ref
            if self._settings.capture_orchestrator_ref_recording_enabled
            else None
        )

        command = RecordWitnessedRun(
            name=f"Witnessed capture {observation.capture_code}",
            plan_id=plan_id,
            capture_code=observation.capture_code,
            monitor_source_id=RUN_WITNESS_MONITOR_SOURCE_ID,
            trigger="Monitor",
            capture_precondition_bypass_snapshot=self._build_precondition_bypass_snapshot(
                observation.capture_code
            ),
            orchestrator_ref=orchestrator_ref,
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
            orchestrator_ref_scheme=(
                orchestrator_ref.scheme if orchestrator_ref is not None else None
            ),
            orchestrator_ref_value=(
                orchestrator_ref.value if orchestrator_ref is not None else None
            ),
        )
        # Concurrent, not sequential: both readers do their own PV
        # sweep and neither depends on the other's result, so awaiting
        # them back to back would double this loop's stall time for no
        # correctness benefit -- exactly what this single-consumer path
        # must not do (see this method's own "must not block" framing
        # elsewhere in this module). Both readers already catch every
        # failure internally, so a plain gather needs no
        # return_exceptions.
        await asyncio.gather(
            self._read_baseline(observation.capture_code, run_id),
            self._read_experiment_identity(observation.capture_code, run_id),
        )

    async def _read_baseline(self, capture_code: str, run_id: UUID) -> None:
        """Slice 12: read the genesis-baseline PVs once, right after a
        successful promotion.

        By this point the promotion has already fully committed
        (`_open_captures` updated, `run_witness.promoted` logged), so a
        baseline-read failure must never unwind or retry it. Gated on
        BOTH a reader being configured (main.py wires one whenever
        `capture_baseline_pvs` is declared) and the fourth kill switch,
        `capture_baseline_recording_enabled`; `CaptureBaselineReader`
        itself catches every failure internally (see its own module
        docstring), the outer try/except here is defense in depth,
        mirroring how `run_witness_loop` already wraps
        `feeder.flush_capture` the same way.
        """
        if self._baseline_reader is None or not self._settings.capture_baseline_recording_enabled:
            return
        try:
            await self._baseline_reader.read(capture_code, run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception(
                "run_witness.baseline_read_failed",
                capture_code=capture_code,
                run_id=str(run_id),
            )

    async def _read_experiment_identity(self, capture_code: str, run_id: UUID) -> None:
        """Slice 14a: vault the proposal / ESAF / ESAF-DOI PVs once,
        right after a successful promotion.

        Same posture as `_read_baseline`: the promotion has already
        fully committed by this point, so a read/vault failure must
        never unwind or retry it. Gated on BOTH a reader being
        configured (main.py wires one whenever
        `capture_experiment_identity_pvs` is declared) and the sixth
        kill switch, `capture_experiment_identity_recording_enabled`;
        `CaptureExperimentIdentityReader` itself catches every failure
        internally (see its own module docstring), the outer
        try/except here is defense in depth, mirroring
        `_read_baseline`'s identical wrapper.
        """
        if (
            self._experiment_identity_reader is None
            or not self._settings.capture_experiment_identity_recording_enabled
        ):
            return
        try:
            await self._experiment_identity_reader.read(capture_code, run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception(
                "run_witness.experiment_identity_read_failed",
                capture_code=capture_code,
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
        # Slice 13: same reasoning, for the retained full_file_name
        # reading and its BEGUN reference point.
        self._last_capture_path.pop(code, None)
        self._begun_at.pop(code, None)
        # DELIBERATELY does NOT pop `_last_orchestrator_ref` here, unlike
        # every other retained dict above: a run uid is written BEFORE
        # the capture it names begins, so a reading retained at the
        # moment a stale Run's un-observed terminal is discovered almost
        # certainly describes the INCOMING new capture this method is
        # about to hand off to `_promote`, not the stale one being
        # closed. Clearing it here would throw away the very evidence
        # `_promote`'s own `_consume_orchestrator_ref` call is about to
        # correctly consume.
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
        # Resolve and write BEFORE evicting: `_write_capture_path` reads
        # `_last_capture_path` / `_begun_at` via `_resolve_capture_path`,
        # so eviction must come after, mirroring the success-only
        # ordering `_last_progress` already follows below.
        await self._write_capture_path(code, run_id)
        self._open_captures.pop(code, None)
        # Success path only, mirroring `_open_captures` immediately
        # above: on failure both dicts stay populated so the next
        # BEGUN's truncate-then-promote clears them together, keeping
        # the two eviction states in lockstep.
        self._last_progress.pop(code, None)
        self._last_capture_path.pop(code, None)
        self._begun_at.pop(code, None)
        _log.info(
            "run_witness.outcome_recorded",
            capture_code=code,
            run_id=str(run_id),
            observed_phase=str(observation.phase),
        )

    async def _write_capture_path(self, code: str, run_id: UUID) -> None:
        """Slice 13: resolve and write the observed capture path for
        `code`'s just-recorded terminal, if the dual-clock guard passes.

        By this point `record_witnessed_run_outcome` has already
        succeeded, so (mirroring `_read_baseline`'s exact posture) a
        failure here must be logged and must never unwind it. Gated on
        BOTH a store being configured (`run_witness_lifespan` wires one
        whenever `capture_watch_pvs` declares the `full_file_name` role
        for at least one code) and the fifth kill switch,
        `capture_path_recording_enabled`.

        No resolved value is a normal, expected outcome (never
        observed, or correctly rejected by `_resolve_capture_path`),
        logged at `info`, not `warning`: a missing filename is a fine
        outcome, per the slice's own design lock; a wrong one is not,
        which is exactly what the guard exists to prevent.
        """
        if self._capture_path_store is None or not self._settings.capture_path_recording_enabled:
            return
        resolved = self._resolve_capture_path(code)
        if resolved is None:
            _log.info(
                "run_witness.capture_path_unresolved",
                capture_code=code,
                run_id=str(run_id),
            )
            return
        observed_path, observed_at = resolved
        host, roots = active_scan_transport(self._deps)
        matched_root = matched_storage_root(observed_path, roots)
        try:
            await self._capture_path_store.upsert(
                run_id=run_id,
                observed_path=observed_path,
                observed_at=observed_at,
                created_at=self._deps.clock.now(),
                # Both NULL when the observed path falls under no
                # configured root: the same condition under which
                # `mint_capture_path_locator` refuses to mint. Recording
                # the path with an unknown location is honest and keeps
                # the display read working; what must not happen is
                # inventing a tier the reading does not support.
                host=host if matched_root is not None else None,
                root=matched_root,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # `_log.exception` (unlike `_log.error`) renders the full
            # traceback, whose final line is `str(exc)` -- and asyncpg
            # appends a `DETAIL:` line to a CHECK-violation error that
            # can include the failing row's own column VALUES. That
            # value is `observed_path`, personal data, and this log
            # sink is not the vault: it cannot be erased. Log the
            # exception's class name only, never the object itself.
            _log.error(
                "run_witness.capture_path_write_failed",
                capture_code=code,
                run_id=str(run_id),
                error_class=type(exc).__name__,
            )
            return
        _log.info(
            "run_witness.capture_path_recorded",
            capture_code=code,
            run_id=str(run_id),
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
            capture_code = extract_capture_code(run.external_refs)
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
    operation. A `CapturePreconditionBypassObservation` goes only to
    `recorder.observe_precondition_bypass()` (retains the latest
    reading so the NEXT genesis can stamp it; see `RunWitnessRecorder
    ._build_precondition_bypass_snapshot`): it has no `feeder`
    counterpart, since it is never written as an `AppendObservations`
    row, only carried onto `RunStarted`. A `CapturePathObservation`
    (slice 13) likewise goes only to `recorder.observe_capture_path()`
    (retains the latest reading so a terminal can resolve it through
    the dual-clock guard; see `RunWitnessRecorder._resolve_capture_path`):
    no `feeder` counterpart either, since it never rides
    `AppendObservations` -- it goes to the `run_capture_path` PII
    vault, not the observation logbook. A `CaptureOrchestratorRefObservation`
    likewise goes only to `recorder.observe_orchestrator_ref()` (retains
    the latest reading so the NEXT genesis can attach it through the
    consume-once lead-time guard; see `RunWitnessRecorder
    ._consume_orchestrator_ref`): no `feeder` counterpart either, since
    it rides `RunStarted.external_refs`, never `AppendObservations`. A
    `CaptureLifecycleObservation` on a phase in
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
                if isinstance(observation, CapturePreconditionBypassObservation):
                    if recorder is not None:
                        recorder.observe_precondition_bypass(observation)
                    continue
                if isinstance(observation, CapturePathObservation):
                    if recorder is not None:
                        recorder.observe_capture_path(observation)
                    continue
                if isinstance(observation, CaptureOrchestratorRefObservation):
                    if recorder is not None:
                        recorder.observe_orchestrator_ref(observation)
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
    control_port: ControlPort | None = None,
    capture_baseline_pvs: Mapping[str, Mapping[str, str]] | None = None,
    capture_path_store: CapturePathStore | None = None,
    capture_experiment_identity_pvs: Mapping[str, Mapping[str, str]] | None = None,
    experiment_identity_store: ExperimentIdentityStore | None = None,
    capture_probe_store: CaptureProbeStore | None = None,
) -> AsyncGenerator[RunWitnessRecorder | None]:
    """Run the watcher as a background task for the app's lifetime.

    Yields the constructed `RunWitnessRecorder` (or `None`, in the
    no-`capture_codes` no-op case, or when `record_witnessed_run` is
    not supplied so the recorder stays shadow-only) so a sibling
    composition-root task started later in the same `async with` group
    (for example `status_push_lifespan`) can read its live in-memory
    progress via `progress_readings()` -- the only place that data
    exists, since it is never written to Postgres at substrate rate.

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

    A non-empty `capture_baseline_pvs` (slice 12) additionally requires
    `record_witnessed_run`, `control_port`, and `append_observations`: a
    `CaptureBaselineReader` is built and handed to the recorder, which
    calls it exactly once per successful promotion. Whether a call to it
    actually reads and appends anything is gated separately, inside the
    recorder, by `deps.settings.capture_baseline_recording_enabled` (the
    fourth kill switch) -- declaring the PVs here is necessary but not
    sufficient, mirroring how declaring `capture_watch_pvs` alone does
    not turn on recording either.

    A supplied `capture_path_store` (slice 13) is handed straight to
    the recorder with no extra required-params check: unlike
    `capture_baseline_pvs`, there is no separate reader object to build
    here (the observer already pumps `CapturePathObservation` whenever
    a code's `capture_watch_pvs` declares `full_file_name`; the store
    is only where the recorder writes the RESULT). Whether a write
    actually happens is gated, same pattern as the fourth switch,
    inside the recorder by `deps.settings.capture_path_recording_enabled`
    (the fifth kill switch).

    A non-empty `capture_experiment_identity_pvs` (slice 14a) additionally
    requires `record_witnessed_run`, `control_port`, and
    `experiment_identity_store`: a `CaptureExperimentIdentityReader` is built
    and handed to the recorder, mirroring `capture_baseline_pvs`'s exact
    shape (a separate reader object, unlike `capture_path_store`'s
    handed-straight-through style, because this reader does its own
    `ControlPort.read()` calls rather than consuming an already-pumped
    observation). Whether a call to it actually reads and vaults
    anything is gated separately, inside the recorder, by
    `deps.settings.capture_experiment_identity_recording_enabled` (the
    sixth kill switch).

    A supplied `capture_probe_store` (slice 16) REQUIRES
    `record_witnessed_run` (checked above, before this docstring's own
    baseline/experiment-identity checks): the write is a
    `RunWitnessRecorder` method, so with no recorder constructed the
    store would otherwise be accepted and silently never written to --
    precisely in the shadow-only configuration this store's own kill
    switch exists to serve. Once that prerequisite holds, the store is
    handed straight to the recorder with no separate reader to build
    (the observer already pumps a `reach_tier` on every
    `CaptureLifecycleObservation`), the same shape as `capture_path_store`.
    Whether a row is actually written is gated, same pattern as every
    other store, inside the recorder by
    `deps.settings.capture_probe_recording_enabled` (the seventh kill
    switch) -- which, UNLIKE the third/fourth/fifth/sixth, does not
    require `run_witness_recording_enabled`; see that setting's own
    docstring.
    """
    if not capture_codes:
        yield None
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

    if capture_probe_store is not None and record_witnessed_run is None:
        # The probe write is a RunWitnessRecorder method, and the
        # recorder is only constructed below when record_witnessed_run
        # is supplied. Without this guard, a caller passing
        # capture_probe_store to an otherwise shadow-only lifespan (no
        # record_witnessed_run, no Kernel) would see the store silently
        # never written to -- the drain loop falls to the bare
        # module-level `observe_capture` (log-only) branch instead --
        # in exactly the shadow-only configuration this store's own
        # kill switch is designed to serve.
        msg = "run_witness_lifespan: capture_probe_store requires record_witnessed_run"
        raise ValueError(msg)

    baseline_reader: CaptureBaselineReader | None = None
    if capture_baseline_pvs:
        missing = [
            name
            for name, value in (
                ("record_witnessed_run", record_witnessed_run),
                ("control_port", control_port),
                ("append_observations", append_observations),
            )
            if value is None
        ]
        if missing:
            msg = f"run_witness_lifespan: capture_baseline_pvs requires {', '.join(missing)}"
            raise ValueError(msg)
        # Narrowed by the checks above; deps is not None because
        # record_witnessed_run is not None (see the first check above).
        assert deps is not None
        assert control_port is not None
        assert append_observations is not None
        baseline_reader = CaptureBaselineReader(
            deps=deps,
            control_port=control_port,
            baseline_pvs=capture_baseline_pvs,
            append_observations=append_observations,
            principal_id=CAPTURE_BASELINE_READER_AGENT_ID,
        )

    experiment_identity_reader: CaptureExperimentIdentityReader | None = None
    if capture_experiment_identity_pvs:
        missing = [
            name
            for name, value in (
                ("record_witnessed_run", record_witnessed_run),
                ("control_port", control_port),
                ("experiment_identity_store", experiment_identity_store),
            )
            if value is None
        ]
        if missing:
            msg = (
                "run_witness_lifespan: capture_experiment_identity_pvs requires "
                f"{', '.join(missing)}"
            )
            raise ValueError(msg)
        # Narrowed by the checks above; deps is not None because
        # record_witnessed_run is not None (see the first check above).
        assert deps is not None
        assert control_port is not None
        assert experiment_identity_store is not None
        experiment_identity_reader = CaptureExperimentIdentityReader(
            deps=deps,
            control_port=control_port,
            experiment_identity_pvs=capture_experiment_identity_pvs,
            store=experiment_identity_store,
        )

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
            baseline_reader=baseline_reader,
            capture_path_store=capture_path_store,
            experiment_identity_reader=experiment_identity_reader,
            capture_probe_store=capture_probe_store,
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
        yield recorder
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
