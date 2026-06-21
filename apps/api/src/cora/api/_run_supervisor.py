"""RunSupervisor runtime: the first ACTIVE in-loop agent.

A periodic background task, hosted at the composition root (`cora.api`)
because it issues Run BC commands AND composes Decision BC events; only
`cora.api` may depend on both BCs (the same placement rationale as
`_enclosure_permit_observer`, and the reason it sidesteps the
`test_no_cross_bc_features_imports` ban, which scans BC packages, not the
composition root). See [[project-run-supervisor-design]].

## What it does

Each tick, for every in-flight Run, it reads facility beam availability
ONCE and decides a disposition:

  - `Continue`  -- beam is available (or its quality is unknown): no action.
  - `Hold`      -- beam is DEFINITELY down while the Run is Running: record a
                   Decision(context=RunSupervision, choice=Hold) and issue
                   `hold_run` (linked via `decided_by_decision_id`).
  - `Resume`    -- the gated wind-up. A Run the supervisor itself held is
                   resumed only when the FULL start-safety envelope is good
                   again (an Active clearance covers the scope, every enclosure
                   is Permitted, every needed supply is Available, and the beam
                   is open) AND it has stayed good for the settle window. Records
                   a Decision(choice=Resume) and issues `resume_run`. Off unless
                   `run_supervisor_resume_enabled` (own-holds-only; fail-safe).
  - `SupervisionDeferred` -- beam is still down but the operator RESUMED a Run
                   the supervisor had held: respect the operator (no re-hold),
                   record one deferral Decision. This is the operator-override
                   cool-down (design Lock 9).

Stop / Abort and the quality / progress rules are deferred: they need the
observe-stream that does not exist yet (strawman headline). Beam-unknown
(`quality_ok=False`) takes NO action, per design Lock 4 (never act on
missing data).

## Shadow run-liveness pass (the run-liveness rule, v1)

A separate OBSERVE-ONLY pass flags a Run that has been Running for an
implausibly long time (`now - running_since` past an operator ceiling): the
de-facto-dead scan a human must currently catch by hand. v1 is SHADOW: it only
logs `run_liveness.would_flag` and records no Decision / issues no command. Off
unless `run_liveness_ceiling_seconds` is set (a second gate above
`run_supervisor_enabled`). It keys on `running_since`, a CORA-owned un-spoofable
signal, with its own edge-trigger memory (`liveness`) walled off from the
beam-Hold FSM (`memory`). See [[project-run-liveness-watchdog-design]]; advise
mode (a `Decision(choice=SupervisionQuieted)`) is the gated next rung.

## Fail-safe and bounded

Hold is fail-safe wind-down. Resume is the one wind-UP, and it is gated to
stay fail-safe: it re-checks the same envelope a fresh start passes (any
failed OR unknown signal keeps the Run Held), only ever resumes a Run the
supervisor itself held, and requires a settle window so a flickering beam
cannot flap a Run between Held and Running. Decisions are recorded edge-
triggered (only on a disposition that changes state), so a quiet beam produces
no Decision churn. The runtime gates on `Actor.active`, so deactivating the
supervisor Actor stops it.

## Authorization

Commands flow through the normal bound handler (Authorize port + decider).
Under the default `AllowAllAuthorize` the supervisor is permitted; under
`TrustAuthorize` the operator's configured Policy must grant this principal
HoldRun and (for the gated wind-up) ResumeRun. No bypass (design Lock 5).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_run_supervisor import RUN_SUPERVISOR_AGENT_ID
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_SUPERVISION,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    event_type_name,
    to_payload,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.equipment.aggregates.asset import load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import load_method
from cora.recipe.aggregates.plan import load_plan
from cora.recipe.aggregates.practice import load_practice
from cora.run.adapters import PostgresRunChannelLookup
from cora.run.aggregates.run import (
    RunBeamAvailabilityUnknownError,
    RunCannotHoldError,
    RunCannotResumeError,
    RunClearanceCoverageMismatchError,
    RunEnclosureCoverageMismatchError,
    RunNotFoundError,
    RunRequiresActiveClearanceError,
    RunRequiresAvailableSupplyError,
    RunRequiresOpenBeamShuttersError,
    RunRequiresPermittedEnclosureError,
    RunSupplyCoverageMismatchError,
    check_safety_envelope,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.hold_run import HoldRun
from cora.run.features.list_runs import ListRuns
from cora.run.features.resume_run import ResumeRun
from cora.run.ports import InMemoryRunChannelLookup
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.beam_availability_lookup import (
        BeamAvailabilityLookup,
        BeamAvailabilityLookupResult,
    )
    from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
    from cora.run.features.hold_run.handler import Handler as HoldRunHandler
    from cora.run.features.list_runs import RunSummaryItem
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.run.features.list_runs.query import RunStatusFilter
    from cora.run.features.resume_run.handler import Handler as ResumeRunHandler
    from cora.run.ports import RunChannelLookup

_log = get_logger(__name__)

_RULE = "agent:RunSupervisor:v1"
_COMMAND_NAME = "RunSupervisorTick"
_STREAM_TYPE = "Decision"
_DEFAULT_INTERVAL_SECONDS = 30.0
_PAGE_LIMIT = 100

# Per-Run supervisor memory values (in-process, edge-trigger + cool-down).
_MEM_HELD = "held_by_supervisor"
_MEM_DEFERRED = "deferred_after_resume"


@dataclass(frozen=True)
class SupervisionOutcome:
    """Result of evaluating one Run against the v1 rules.

    `choice` is a RunSupervisionChoice value. `new_memory` is the per-Run
    memory to retain (None clears it). `record` gates whether a Decision is
    written this tick (edge-triggered). `issue_hold` gates the HoldRun command;
    `issue_resume` gates the ResumeRun command (the gated wind-up).
    """

    choice: str
    new_memory: str | None
    record: bool
    issue_hold: bool
    issue_resume: bool = False


# Maps each start-safety gate error to a short label for Decision evidence
# and logging. The keys are the exact errors `check_safety_envelope` raises.
_ENVELOPE_GATE: dict[type[Exception], str] = {
    RunRequiresActiveClearanceError: "clearance",
    RunClearanceCoverageMismatchError: "clearance",
    RunRequiresAvailableSupplyError: "supply",
    RunSupplyCoverageMismatchError: "supply",
    RunRequiresPermittedEnclosureError: "enclosure",
    RunEnclosureCoverageMismatchError: "enclosure",
    RunBeamAvailabilityUnknownError: "beam",
    RunRequiresOpenBeamShuttersError: "beam",
}
_ENVELOPE_ERRORS = tuple(_ENVELOPE_GATE)


@dataclass(frozen=True)
class EnvelopeCheck:
    """Result of re-checking a held Run's start-safety envelope.

    `ok` is True only when every live-signal gate passes. `failed_gate` is
    the short label of the first failing gate (or a `*_missing` marker when
    an upstream aggregate could not be loaded), for Decision evidence and
    logs; None when ok.
    """

    ok: bool
    failed_gate: str | None


def decide_supervision(
    *,
    run_status: str,
    beam: BeamAvailabilityLookupResult,
    prior: str | None,
    envelope_ok: bool | None = None,
    settle_ticks_met: bool = False,
) -> SupervisionOutcome:
    """Pure supervision rule for one Run (no I/O).

    Hold path (Running): beam is "definitely down" only when the read
    quality is Good and a shutter/permit is closed; a non-Good read is
    "unknown" and yields no action (Lock 4).

    Resume path (Held): the gated wind-up. A Held Run the supervisor
    itself holds (`prior == _MEM_HELD`) is resumed only when the full
    start-safety envelope is good again (`envelope_ok`, computed by the
    caller via `check_safety_envelope`) AND it has stayed good for the
    settle window (`settle_ticks_met`, anti-flap). The envelope check and
    the beam reading are the caller's I/O; this rule consumes their
    booleans. A Held Run the supervisor did NOT hold (`prior` is None /
    DEFERRED) is never auto-resumed (own-holds-only).
    """
    if run_status == "Held":
        if prior == _MEM_HELD and envelope_ok and settle_ticks_met:
            # Wind-up: we held it, the envelope is safe again, and it has
            # been stable. Resume and drop to DEFERRED so a beam re-drop
            # right after does not immediately re-hold (anti-flap).
            return SupervisionOutcome(
                choice="Resume",
                new_memory=_MEM_DEFERRED,
                record=True,
                issue_hold=False,
                issue_resume=True,
            )
        # Held but not ours, or the envelope is not (yet) safe/stable:
        # take no action and keep our memory so we keep watching.
        return SupervisionOutcome(
            choice="Continue", new_memory=prior, record=False, issue_hold=False
        )
    if run_status != "Running":
        return SupervisionOutcome(
            choice="Continue", new_memory=None, record=False, issue_hold=False
        )
    if not beam.quality_ok:
        # Unknown beam: take no action; keep prior memory unchanged.
        return SupervisionOutcome(
            choice="Continue", new_memory=prior, record=False, issue_hold=False
        )
    beam_open = beam.fes_open and beam.sbs_open and beam.fes_permit
    if beam_open:
        return SupervisionOutcome(
            choice="Continue", new_memory=None, record=False, issue_hold=False
        )
    # Beam is definitely down and the Run is Running.
    if prior == _MEM_HELD:
        # The supervisor held this Run, and the operator resumed it while beam
        # is still down: respect the operator, defer once, never re-hold.
        return SupervisionOutcome(
            choice="SupervisionDeferred", new_memory=_MEM_DEFERRED, record=True, issue_hold=False
        )
    if prior == _MEM_DEFERRED:
        return SupervisionOutcome(
            choice="SupervisionDeferred", new_memory=_MEM_DEFERRED, record=False, issue_hold=False
        )
    return SupervisionOutcome(choice="Hold", new_memory=_MEM_HELD, record=True, issue_hold=True)


def is_run_stale(running_since: datetime | None, now: datetime, ceiling_seconds: float) -> bool:
    """Pure Run-liveness rule (no I/O): a Running Run is liveness-stale once it
    has been Running past the operator ceiling without progressing.

    Inclusive boundary: elapsed == ceiling FLAGS (`>=`). A Run with no
    `running_since` (legacy row, or one that started before the column existed)
    is never stale -- it cannot be evaluated, so the rule defers (Lock 4:
    never act on missing data). The signal is `running_since`, a CORA-owned,
    un-spoofable timestamp set on RunStarted and reset on RunResumed.
    """
    return running_since is not None and (now - running_since).total_seconds() >= ceiling_seconds


@dataclass(frozen=True)
class ObservationRuleConfig:
    """Operator config for the shadow observation rules (Rule Q + Rule R).

    Both rules are OFF when their channel name is None. Bundled so the tick
    signature stays legible. Channel names are deployment facts (which channel
    carries the quality / progress signal); the per-Run thresholds
    (snr_limit, expected_observation_interval_seconds) ride RunSummaryItem.
    """

    quality_channel_name: str | None
    stall_channel_name: str | None
    stall_window_factor: float
    stall_hysteresis_ticks: int
    feed_heartbeat_ceiling_seconds: float | None


@dataclass(frozen=True)
class SignalDisposition:
    """Result of a shadow observation rule for one Run (pure, no I/O).

    `would_flag` is the merits breach (quality below limit / stalled),
    computed WITHOUT the simulation gate: shadow mode observes and logs even
    simulated breaches, which is how the sim feeder exercises the rules end to
    end. The is_simulated act-disqualify lands with the advise/act rung. Every
    cannot-tell path (missing signal, disabled rule, dead feeder, beam down,
    degenerate interval) returns would_flag=False with a reason, never a
    confident flag (Lock 4: never act on missing data).
    """

    would_flag: bool
    reason: str


def decide_quality_signal(
    *, latest_value: float | None, snr_limit: float | None
) -> SignalDisposition:
    """Pure Rule Q: flag when a quality channel's latest value is below the
    operator-set limit. None limit = rule disabled; None value = cannot-tell."""
    if snr_limit is None:
        return SignalDisposition(would_flag=False, reason="rule_disabled")
    if latest_value is None:
        return SignalDisposition(would_flag=False, reason="no_observation")
    if latest_value < snr_limit:
        return SignalDisposition(would_flag=True, reason="quality_below_limit")
    return SignalDisposition(would_flag=False, reason="within_limits")


def decide_signal_stall(
    *,
    count_since: int,
    window_seconds: float,
    expected_interval: float | None,
    feed_alive: bool,
    beam_open: bool,
) -> SignalDisposition:
    """Pure Rule R (one tick): flag when no values arrived in a window that
    covers at least one expected interval, while the beam is up and the feeder
    heartbeat is fresh. Every cannot-tell branch defers (Lock 4). Multi-tick
    hysteresis (anti-flap for brief beam pauses / top-ups) is the caller's."""
    if expected_interval is None:
        return SignalDisposition(would_flag=False, reason="rule_disabled")
    if expected_interval <= 0:
        return SignalDisposition(would_flag=False, reason="degenerate_interval")
    if window_seconds < expected_interval:
        return SignalDisposition(would_flag=False, reason="window_too_short")
    if not feed_alive:
        return SignalDisposition(would_flag=False, reason="feed_dead")
    if not beam_open:
        return SignalDisposition(would_flag=False, reason="beam_down")
    if count_since == 0:
        return SignalDisposition(would_flag=True, reason="stalled")
    return SignalDisposition(would_flag=False, reason="arriving")


def _reasoning_for(choice: str) -> str:
    if choice == "Hold":
        return (
            "Beam unavailable (a shutter or the FES permit is closed); held the "
            "Run to avoid acquiring on absent beam. Resumable once beam returns."
        )
    if choice == "Resume":
        return (
            "Beam returned and the full start-safety envelope is satisfied again "
            "(an Active clearance covers the scope, every enclosure is Permitted, "
            "every needed supply is Available, and the shutters are open); resumed "
            "the Run the supervisor itself held."
        )
    return (
        "Beam still unavailable but the operator resumed the Run; deferring to "
        "the operator (no re-hold for this outage)."
    )


async def _record_decision(
    deps: Kernel,
    *,
    decision_id: UUID,
    run_id: UUID,
    choice: str,
    beam: BeamAvailabilityLookupResult,
    extra_inputs: dict[str, str] | None = None,
) -> None:
    """Compose and append one DecisionRegistered (Decision BC genesis).

    Mirrors the subscriber `_compose_and_append` shape (public Decision VOs
    only). A ConcurrencyError means a prior tick already wrote this id (rare
    cross-restart re-derivation); treat as success. `extra_inputs` adds
    disposition-specific evidence (e.g. the resume envelope + settle count).
    """
    now = deps.clock.now()
    decision_inputs = {
        "run_id": str(run_id),
        "beam_fes_open": str(beam.fes_open),
        "beam_sbs_open": str(beam.sbs_open),
        "beam_fes_permit": str(beam.fes_permit),
        "beam_quality_ok": str(beam.quality_ok),
    }
    if extra_inputs:
        decision_inputs.update(extra_inputs)
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(RUN_SUPERVISOR_AGENT_ID),
        context=DecisionContext(DECISION_CONTEXT_RUN_SUPERVISION).value,
        choice=DecisionChoice(choice).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(_RULE).value,
        reasoning=validate_reasoning(_reasoning_for(choice)),
        confidence=validate_confidence(None),
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=validate_inputs(decision_inputs),
        reasoning_signature=None,
        occurred_at=now,
    )
    new_event = to_new_event(
        event_type=event_type_name(domain_event),
        payload=to_payload(domain_event),
        occurred_at=now,
        event_id=uuid5(decision_id, "event:0"),
        command_name=_COMMAND_NAME,
        correlation_id=deps.id_generator.new_id(),
        causation_id=None,
        principal_id=RUN_SUPERVISOR_AGENT_ID,
    )
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info("run_supervisor.decision_already_written", choice=choice)


async def _record_supervision_advice(
    deps: Kernel,
    *,
    run_id: UUID,
    choice: str,
    inputs: dict[str, str],
    reasoning: str,
) -> None:
    """Append one advise-rung DecisionRegistered for a shadow-rule breach edge.

    The advise rung: when `run_supervisor_advise_enabled` is on, the run-liveness
    / quality / stall rules emit ONE Decision(context=RunSupervision,
    choice=SupervisionQuieted/Breached/Stalled) per breach edge for a human, and
    still issue NO command (Decision-only). Beam-free (unlike `_record_decision`):
    the liveness rule runs before the beam read, and the quality/stall evidence is
    the rule's own inputs. Edge-triggered by the caller's per-rule memory, so a
    fresh id per episode is fine; a ConcurrencyError on cross-restart
    re-derivation is treated as success (same posture as `_record_decision`).
    """
    now = deps.clock.now()
    decision_id = deps.id_generator.new_id()
    decision_inputs = {"run_id": str(run_id), **inputs}
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(RUN_SUPERVISOR_AGENT_ID),
        context=DecisionContext(DECISION_CONTEXT_RUN_SUPERVISION).value,
        choice=DecisionChoice(choice).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(_RULE).value,
        reasoning=validate_reasoning(reasoning),
        confidence=validate_confidence(None),
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        inputs=validate_inputs(decision_inputs),
        reasoning_signature=None,
        occurred_at=now,
    )
    new_event = to_new_event(
        event_type=event_type_name(domain_event),
        payload=to_payload(domain_event),
        occurred_at=now,
        event_id=uuid5(decision_id, "event:0"),
        command_name=_COMMAND_NAME,
        correlation_id=deps.id_generator.new_id(),
        causation_id=None,
        principal_id=RUN_SUPERVISOR_AGENT_ID,
    )
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info("run_supervisor.decision_already_written", choice=choice)


async def _issue_hold(
    deps: Kernel,
    hold_run: HoldRunHandler,
    *,
    run_id: UUID,
    decision_id: UUID,
) -> None:
    """Issue HoldRun through the authorized handler; benign no-op on state race."""
    try:
        await hold_run(
            HoldRun(run_id=run_id, decided_by_decision_id=decision_id),
            principal_id=RUN_SUPERVISOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    except (RunCannotHoldError, RunNotFoundError) as exc:
        # The Run changed under us between read and issue (someone else acted,
        # or it terminated): a benign no-op, not an error.
        _log.info("run_supervisor.hold_skipped", run_id=str(run_id), reason=type(exc).__name__)
    except UnauthorizedError:
        # Configuration fault: the supervisor principal is not granted HoldRun.
        # Log loudly; take no autonomous action.
        _log.warning("run_supervisor.hold_unauthorized", run_id=str(run_id))


async def _issue_resume(
    deps: Kernel,
    resume_run: ResumeRunHandler,
    *,
    run_id: UUID,
    decision_id: UUID,
) -> None:
    """Issue ResumeRun through the authorized handler; benign no-op on state race."""
    try:
        await resume_run(
            ResumeRun(run_id=run_id, decided_by_decision_id=decision_id),
            principal_id=RUN_SUPERVISOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    except (RunCannotResumeError, RunNotFoundError) as exc:
        # The Run changed under us between read and issue (an operator resumed
        # it, or it terminated): a benign no-op, not an error.
        _log.info("run_supervisor.resume_skipped", run_id=str(run_id), reason=type(exc).__name__)
    except UnauthorizedError:
        # Configuration fault: the supervisor principal is not granted ResumeRun.
        # Log loudly; take no autonomous action (the Run stays Held).
        _log.warning("run_supervisor.resume_unauthorized", run_id=str(run_id))


async def _assemble_and_check_envelope(
    deps: Kernel,
    item: RunSummaryItem,
    beam: BeamAvailabilityLookupResult,
) -> EnvelopeCheck:
    """Re-derive a held Run's start-safety envelope and check it.

    Reproduces the `start_run` handler's load + scope-widening (Plan ->
    Practice -> Method -> Assets, controller + ancestor-chain widening) and
    the four cross-BC lookups, then runs the shared `check_safety_envelope`
    against the SAME `beam` reading the tick already took. A missing upstream
    aggregate (data corruption for a Run that started) is treated as
    not-ok / fail-safe (stay Held) rather than crashing the tick; genuine
    I/O failures propagate to the tick's retry.
    """
    plan = await load_plan(deps.event_store, item.plan_id)
    if plan is None:
        return EnvelopeCheck(ok=False, failed_gate="plan_missing")
    practice = await load_practice(deps.event_store, plan.practice_id)
    if practice is None:
        return EnvelopeCheck(ok=False, failed_gate="practice_missing")
    method = await load_method(deps.event_store, practice.method_id)
    if method is None:
        return EnvelopeCheck(ok=False, failed_gate="method_missing")

    controller_ids: set[UUID] = set()
    for asset_id in sorted(plan.asset_ids, key=str):
        asset = await load_asset(deps.event_store, asset_id)
        if asset is None:
            return EnvelopeCheck(ok=False, failed_gate="asset_missing")
        if asset.controller_id is not None:
            controller_ids.add(asset.controller_id)

    # Scope widening identical to start_run: controller back-refs (one-hop)
    # then the parent_id ancestor closure, so a clearance/enclosure bound to
    # a controller or a containing Unit is in scope exactly as at start.
    scoped_asset_ids = plan.asset_ids | controller_ids
    ancestor_rows = await deps.asset_lookup.ancestors_of(scoped_asset_ids)
    scoped_asset_ids = scoped_asset_ids | {row.id for row in ancestor_rows}

    referencing_clearances = tuple(
        await deps.clearance_lookup.find_covering(
            run_id=item.run_id,
            subject_id=item.subject_id,
            asset_ids=scoped_asset_ids,
        )
    )
    located_in_enclosure_ids = frozenset(
        row.located_in_enclosure_id
        for row in ancestor_rows
        if row.located_in_enclosure_id is not None
    )
    referencing_enclosures = tuple(
        await deps.enclosure_lookup.find_by_ids(enclosure_ids=located_in_enclosure_ids)
    )
    needed_supplies_satisfaction: dict[str, tuple[SupplyLookupResult, ...]] = {}
    if method.needed_supplies:
        satisfaction = await deps.supply_lookup.find_supplies_by_kind(kinds=method.needed_supplies)
        needed_supplies_satisfaction = {kind: tuple(refs) for kind, refs in satisfaction.items()}

    try:
        check_safety_envelope(
            run_id=item.run_id,
            referencing_clearances=referencing_clearances,
            needed_supplies_snapshot=method.needed_supplies,
            needed_supplies_satisfaction=needed_supplies_satisfaction,
            referencing_enclosures=referencing_enclosures,
            beam_availability=beam,
        )
    except _ENVELOPE_ERRORS as exc:
        return EnvelopeCheck(ok=False, failed_gate=_ENVELOPE_GATE[type(exc)])
    return EnvelopeCheck(ok=True, failed_gate=None)


def _apply_memory(memory: dict[UUID, str], run_id: UUID, outcome: SupervisionOutcome) -> None:
    """Persist the per-Run supervisor memory transition (None clears it)."""
    if outcome.new_memory is None:
        memory.pop(run_id, None)
    else:
        memory[run_id] = outcome.new_memory


async def _drain_runs(
    list_runs: ListRunsHandler, deps: Kernel, *, status: RunStatusFilter
) -> list[RunSummaryItem]:
    """Page through list_runs for a single status; return all rows."""
    items: list[RunSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_runs(
            ListRuns(status=status, cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=RUN_SUPERVISOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


async def _observe_run_signals(
    deps: Kernel,
    channel_lookup: RunChannelLookup,
    rules_config: ObservationRuleConfig,
    running: list[RunSummaryItem],
    beam: BeamAvailabilityLookupResult,
    *,
    quality: set[UUID],
    stall: set[UUID],
    stall_streak: dict[UUID, int],
    feed_dead_warned: set[UUID],
    advise_enabled: bool,
) -> None:
    """Observation rules (Rule Q + Rule R): shadow log + optional advise.

    Always logs `run_quality.would_flag` / `run_stall.would_flag` and issues NO
    command. When `advise_enabled`, ALSO records one Decision per breach EDGE
    (SupervisionBreached for Rule Q, SupervisionStalled for Rule R); still no
    command (advise rung). Each rule keeps its OWN edge-trigger state (`quality`,
    `stall` + the `stall_streak` hysteresis counter), walled off from the
    beam-Hold FSM memory, the liveness set, and each other. Reuses the tick's
    single beam read for Rule R's beam-awareness.
    """
    now = deps.clock.now()
    beam_open = beam.quality_ok and beam.fes_open and beam.sbs_open and beam.fes_permit
    for item in running:
        run_id = item.run_id

        # Rule Q (quality-within-limits): edge-triggered, no hysteresis (a value
        # below the limit is a stable signal, unlike a missed beam tick).
        quality_channel = rules_config.quality_channel_name
        if quality_channel is not None and item.snr_limit is not None:
            latest = await channel_lookup.read_run_channel_latest(
                run_id=run_id, channel_name=quality_channel
            )
            disp = decide_quality_signal(
                latest_value=latest.value if latest is not None else None,
                snr_limit=item.snr_limit,
            )
            if disp.would_flag and run_id not in quality:
                quality.add(run_id)
                _log.info(
                    "run_quality.would_flag",
                    run_id=str(run_id),
                    channel=quality_channel,
                    value=latest.value if latest is not None else None,
                    snr_limit=item.snr_limit,
                    is_simulated=latest.is_simulated if latest is not None else None,
                )
                if advise_enabled:
                    await _record_supervision_advice(
                        deps,
                        run_id=run_id,
                        choice="SupervisionBreached",
                        inputs={
                            "channel": quality_channel,
                            "value": str(latest.value) if latest is not None else "None",
                            "snr_limit": str(item.snr_limit),
                            "is_simulated": str(latest.is_simulated)
                            if latest is not None
                            else "None",
                        },
                        reasoning=(
                            "A quality channel's latest value crossed below the "
                            "operator-set limit; flagged for a human to review data "
                            "quality. No command issued (advise rung)."
                        ),
                    )
            elif not disp.would_flag:
                quality.discard(run_id)

        # Rule R (rate-dropout / stall): beam-aware + dead-feeder-aware + multi-
        # tick hysteresis. Active only when the channel, the per-Run interval,
        # and the feeder-health ceiling are all set.
        stall_channel = rules_config.stall_channel_name
        interval = item.expected_observation_interval_seconds
        ceiling = rules_config.feed_heartbeat_ceiling_seconds
        if stall_channel is not None and interval is not None and ceiling is not None:
            health = await channel_lookup.read_feed_health(run_id=run_id)
            feed_alive = (
                health.latest_heartbeat_recorded_at is not None
                and (now - health.latest_heartbeat_recorded_at).total_seconds() <= ceiling
            )
            # Surface a dead / never-seen feeder LOUDLY (edge-triggered) so a
            # misconfigured deployment is not silently stuck deferring forever.
            if not feed_alive:
                if run_id not in feed_dead_warned:
                    feed_dead_warned.add(run_id)
                    _log.warning(
                        "run_stall.feeder_unhealthy",
                        run_id=str(run_id),
                        never_seen=health.latest_heartbeat_recorded_at is None,
                    )
            else:
                feed_dead_warned.discard(run_id)

            window_seconds = rules_config.stall_window_factor * interval
            signal = await channel_lookup.read_run_channel_window(
                run_id=run_id,
                channel_name=stall_channel,
                since=now - timedelta(seconds=window_seconds),
            )
            disp = decide_signal_stall(
                count_since=signal.count_since,
                window_seconds=window_seconds,
                expected_interval=interval,
                feed_alive=feed_alive,
                beam_open=beam_open,
            )
            if disp.would_flag:
                streak = stall_streak.get(run_id, 0) + 1
                stall_streak[run_id] = streak
                if streak >= rules_config.stall_hysteresis_ticks and run_id not in stall:
                    stall.add(run_id)
                    _log.info(
                        "run_stall.would_flag",
                        run_id=str(run_id),
                        channel=stall_channel,
                        window_seconds=window_seconds,
                        expected_interval=interval,
                        streak=streak,
                        is_simulated=signal.is_simulated_window,
                    )
                    if advise_enabled:
                        await _record_supervision_advice(
                            deps,
                            run_id=run_id,
                            choice="SupervisionStalled",
                            inputs={
                                "channel": stall_channel,
                                "window_seconds": str(window_seconds),
                                "expected_interval": str(interval),
                                "is_simulated": str(signal.is_simulated_window),
                            },
                            reasoning=(
                                "A live observation channel stopped arriving (no values "
                                "for longer than the expected interval) while the beam is "
                                "up and the feeder is alive; flagged as a possible stall. "
                                "No command issued (advise rung)."
                            ),
                        )
            else:
                stall_streak.pop(run_id, None)
                stall.discard(run_id)


async def _supervise_tick(
    *,
    deps: Kernel,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    resume_run: ResumeRunHandler,
    beam_lookup: BeamAvailabilityLookup,
    channel_lookup: RunChannelLookup,
    rules_config: ObservationRuleConfig,
    memory: dict[UUID, str],
    settle: dict[UUID, int],
    liveness: set[UUID],
    quality: set[UUID],
    stall: set[UUID],
    stall_streak: dict[UUID, int],
    feed_dead_warned: set[UUID],
    resume_enabled: bool,
    resume_settle_ticks: int,
    liveness_ceiling_seconds: float | None,
    advise_enabled: bool,
) -> None:
    """One supervision pass over all in-flight Runs (hold + gated resume +
    shadow liveness + optional advise)."""
    actor = await load_actor(deps.event_store, RUN_SUPERVISOR_AGENT_ID)
    if actor is None or not actor.active:
        # Supervisor not seeded yet, or deactivated by an operator: stand down.
        return

    running = await _drain_runs(list_runs, deps, status="Running")
    held = await _drain_runs(list_runs, deps, status="Held")
    inflight_ids = {item.run_id for item in running} | {item.run_id for item in held}
    for run_id in list(memory):
        if run_id not in inflight_ids:
            del memory[run_id]
    for run_id in list(settle):
        if run_id not in inflight_ids:
            del settle[run_id]
    for run_id in list(liveness):
        if run_id not in inflight_ids:
            liveness.discard(run_id)
    for run_id in list(stall_streak):
        if run_id not in inflight_ids:
            del stall_streak[run_id]
    for run_id in list(quality):
        if run_id not in inflight_ids:
            quality.discard(run_id)
    for run_id in list(stall):
        if run_id not in inflight_ids:
            stall.discard(run_id)
    for run_id in list(feed_dead_warned):
        if run_id not in inflight_ids:
            feed_dead_warned.discard(run_id)

    # Shadow run-liveness pass (the run-liveness rule, v1): OBSERVE-ONLY. It logs
    # which Running Runs it WOULD flag as implausibly long (now - running_since
    # past the operator ceiling) and records nothing, issues no command. Run
    # before the beam read so it is independent of beam I/O. Off unless the
    # operator set a ceiling. Edge-triggered via `liveness` (a set walled off
    # from the beam-Hold `memory`): log once per stall episode; clearing on
    # not-stale lets it re-log if a resumed Run goes stale again.
    if liveness_ceiling_seconds is not None:
        now = deps.clock.now()
        for item in running:
            running_since = item.running_since
            if running_since is not None and is_run_stale(
                running_since, now, liveness_ceiling_seconds
            ):
                if item.run_id not in liveness:
                    liveness.add(item.run_id)
                    running_seconds = int((now - running_since).total_seconds())
                    _log.info(
                        "run_liveness.would_flag",
                        run_id=str(item.run_id),
                        running_seconds=running_seconds,
                        ceiling_seconds=liveness_ceiling_seconds,
                    )
                    if advise_enabled:
                        await _record_supervision_advice(
                            deps,
                            run_id=item.run_id,
                            choice="SupervisionQuieted",
                            inputs={
                                "running_seconds": str(running_seconds),
                                "ceiling_seconds": str(liveness_ceiling_seconds),
                            },
                            reasoning=(
                                "The Run has been Running far past the operator run-age "
                                "ceiling without progressing; flagged for a human to check "
                                "whether it is hung. No command issued (advise rung)."
                            ),
                        )
            else:
                liveness.discard(item.run_id)

    # Own-holds-only: only a Held Run the supervisor itself holds is a resume
    # candidate. Empty unless the wind-up is explicitly enabled.
    resume_candidates = (
        [item for item in held if memory.get(item.run_id) == _MEM_HELD] if resume_enabled else []
    )
    if not running and not resume_candidates:
        return

    beam = await beam_lookup.read()

    # Hold pass (Running Runs).
    for item in running:
        outcome = decide_supervision(
            run_status=item.status, beam=beam, prior=memory.get(item.run_id)
        )
        _apply_memory(memory, item.run_id, outcome)
        if not outcome.record:
            continue
        decision_id = deps.id_generator.new_id()
        await _record_decision(
            deps, decision_id=decision_id, run_id=item.run_id, choice=outcome.choice, beam=beam
        )
        if outcome.issue_hold:
            await _issue_hold(deps, hold_run, run_id=item.run_id, decision_id=decision_id)

    # Shadow observation rules (Rule Q + Rule R): OBSERVE-ONLY, reusing the
    # single beam read above for Rule R's beam-awareness. No Decision, no
    # command; own walled-off edge-trigger state.
    await _observe_run_signals(
        deps,
        channel_lookup,
        rules_config,
        running,
        beam,
        quality=quality,
        stall=stall,
        stall_streak=stall_streak,
        feed_dead_warned=feed_dead_warned,
        advise_enabled=advise_enabled,
    )

    # Gated resume pass (Held Runs the supervisor holds).
    for item in resume_candidates:
        check = await _assemble_and_check_envelope(deps, item, beam)
        if check.ok:
            settle[item.run_id] = settle.get(item.run_id, 0) + 1
        else:
            settle.pop(item.run_id, None)
            _log.info(
                "run_supervisor.resume_blocked",
                run_id=str(item.run_id),
                failed_gate=check.failed_gate,
            )
        settle_count = settle.get(item.run_id, 0)
        outcome = decide_supervision(
            run_status=item.status,
            beam=beam,
            prior=memory.get(item.run_id),
            envelope_ok=check.ok,
            settle_ticks_met=settle_count >= resume_settle_ticks,
        )
        _apply_memory(memory, item.run_id, outcome)
        if not outcome.record:
            continue
        decision_id = deps.id_generator.new_id()
        await _record_decision(
            deps,
            decision_id=decision_id,
            run_id=item.run_id,
            choice=outcome.choice,
            beam=beam,
            extra_inputs={"envelope_ok": str(check.ok), "settle_ticks": str(settle_count)},
        )
        if outcome.issue_resume:
            # Resumed: drop the settle counter (the Run is leaving the
            # held-by-us candidate set as it returns to Running).
            settle.pop(item.run_id, None)
            await _issue_resume(deps, resume_run, run_id=item.run_id, decision_id=decision_id)


async def _supervise_loop(
    deps: Kernel,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    resume_run: ResumeRunHandler,
    beam_lookup: BeamAvailabilityLookup,
    channel_lookup: RunChannelLookup,
    rules_config: ObservationRuleConfig,
    interval_seconds: float,
    resume_enabled: bool,
    resume_settle_ticks: int,
    liveness_ceiling_seconds: float | None,
    advise_enabled: bool,
) -> None:
    """Periodic supervision loop. A failed tick is logged; the next tick retries."""
    memory: dict[UUID, str] = {}
    settle: dict[UUID, int] = {}
    liveness: set[UUID] = set()
    quality: set[UUID] = set()
    stall: set[UUID] = set()
    stall_streak: dict[UUID, int] = {}
    feed_dead_warned: set[UUID] = set()
    while True:
        try:
            await _supervise_tick(
                deps=deps,
                list_runs=list_runs,
                hold_run=hold_run,
                resume_run=resume_run,
                beam_lookup=beam_lookup,
                channel_lookup=channel_lookup,
                rules_config=rules_config,
                memory=memory,
                settle=settle,
                liveness=liveness,
                quality=quality,
                stall=stall,
                stall_streak=stall_streak,
                feed_dead_warned=feed_dead_warned,
                resume_enabled=resume_enabled,
                resume_settle_ticks=resume_settle_ticks,
                liveness_ceiling_seconds=liveness_ceiling_seconds,
                advise_enabled=advise_enabled,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("run_supervisor.tick_failed")
        await asyncio.sleep(interval_seconds)


def _default_channel_lookup(deps: Kernel) -> RunChannelLookup:
    """Build the BC-local RunChannelLookup: Postgres when a pool is present,
    else the in-memory stub (app_env=test). Mirrors the wire_run
    ObservationStore default; not promoted to the Kernel."""
    if deps.pool is not None:
        return PostgresRunChannelLookup(deps.pool)
    return InMemoryRunChannelLookup()


@contextlib.asynccontextmanager
async def run_supervisor_lifespan(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    resume_run: ResumeRunHandler,
    beam_lookup: BeamAvailabilityLookup | None = None,
    channel_lookup: RunChannelLookup | None = None,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the RunSupervisor loop for the duration of the context.

    No-op unless `settings.run_supervisor_enabled` is True (default off, so a
    deployment opts in explicitly). The gated wind-up is a separate opt-in
    (`run_supervisor_resume_enabled`, also default off) so a deployment may
    run auto-hold without auto-resume. The shadow observation rules are a
    further opt-in (their channel-name settings, default None).
    """
    if not deps.settings.run_supervisor_enabled:
        _log.info("run_supervisor.skipped", reason="disabled")
        yield
        return

    interval = (
        interval_seconds
        if interval_seconds is not None
        else deps.settings.run_supervisor_tick_seconds
    )
    lookup = beam_lookup if beam_lookup is not None else deps.beam_availability_lookup
    # RunChannelLookup is Run-BC-local (not a Kernel field, mirroring the
    # BC-internal ObservationStore): construct it here at the composition root.
    channels = channel_lookup if channel_lookup is not None else _default_channel_lookup(deps)
    resume_enabled = deps.settings.run_supervisor_resume_enabled
    resume_settle_ticks = deps.settings.run_supervisor_resume_settle_ticks
    liveness_ceiling_seconds = deps.settings.run_liveness_ceiling_seconds
    advise_enabled = deps.settings.run_supervisor_advise_enabled
    rules_config = ObservationRuleConfig(
        quality_channel_name=deps.settings.run_quality_channel_name,
        stall_channel_name=deps.settings.run_stall_channel_name,
        stall_window_factor=deps.settings.run_stall_window_factor,
        stall_hysteresis_ticks=deps.settings.run_stall_hysteresis_ticks,
        feed_heartbeat_ceiling_seconds=deps.settings.run_feed_heartbeat_ceiling_seconds,
    )
    _log.info(
        "run_supervisor.started",
        interval_seconds=interval,
        resume_enabled=resume_enabled,
        liveness_ceiling_seconds=liveness_ceiling_seconds,
        quality_channel=rules_config.quality_channel_name,
        stall_channel=rules_config.stall_channel_name,
        advise_enabled=advise_enabled,
    )
    task = asyncio.create_task(
        _supervise_loop(
            deps,
            list_runs,
            hold_run,
            resume_run,
            lookup,
            channels,
            rules_config,
            interval,
            resume_enabled,
            resume_settle_ticks,
            liveness_ceiling_seconds,
            advise_enabled,
        ),
        name="run-supervisor",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("run_supervisor.stopped")


__all__ = [
    "EnvelopeCheck",
    "ObservationRuleConfig",
    "SignalDisposition",
    "SupervisionOutcome",
    "decide_quality_signal",
    "decide_signal_stall",
    "decide_supervision",
    "is_run_stale",
    "run_supervisor_lifespan",
]
