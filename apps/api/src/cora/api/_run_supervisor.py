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
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import RunCannotHoldError, RunNotFoundError
from cora.run.errors import UnauthorizedError
from cora.run.features.hold_run import HoldRun
from cora.run.features.list_runs import ListRuns
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.beam_availability_lookup import (
        BeamAvailabilityLookup,
        BeamAvailabilityLookupResult,
    )
    from cora.run.features.hold_run.handler import Handler as HoldRunHandler
    from cora.run.features.list_runs import RunSummaryItem
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.run.features.list_runs.query import RunStatusFilter

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
) -> None:
    """Compose and append one DecisionRegistered (Decision BC genesis).

    Mirrors the subscriber `_compose_and_append` shape (public Decision VOs
    only). A ConcurrencyError means a prior tick already wrote this id (rare
    cross-restart re-derivation); treat as success.
    """
    now = deps.clock.now()
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
        inputs=validate_inputs(
            {
                "run_id": str(run_id),
                "beam_fes_open": str(beam.fes_open),
                "beam_sbs_open": str(beam.sbs_open),
                "beam_fes_permit": str(beam.fes_permit),
                "beam_quality_ok": str(beam.quality_ok),
            }
        ),
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


async def _supervise_tick(
    *,
    deps: Kernel,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    beam_lookup: BeamAvailabilityLookup,
    memory: dict[UUID, str],
) -> None:
    """One supervision pass over all in-flight Runs."""
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

    if not running:
        return

    beam = await beam_lookup.read_beam_availability()
    for item in running:
        outcome = decide_supervision(
            run_status=item.status, beam=beam, prior=memory.get(item.run_id)
        )
        if outcome.new_memory is None:
            memory.pop(item.run_id, None)
        else:
            memory[item.run_id] = outcome.new_memory
        if not outcome.record:
            continue
        decision_id = deps.id_generator.new_id()
        await _record_decision(
            deps, decision_id=decision_id, run_id=item.run_id, choice=outcome.choice, beam=beam
        )
        if outcome.issue_hold:
            await _issue_hold(deps, hold_run, run_id=item.run_id, decision_id=decision_id)


async def _supervise_loop(
    deps: Kernel,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    beam_lookup: BeamAvailabilityLookup,
    interval_seconds: float,
) -> None:
    """Periodic supervision loop. A failed tick is logged; the next tick retries."""
    memory: dict[UUID, str] = {}
    while True:
        try:
            await _supervise_tick(
                deps=deps,
                list_runs=list_runs,
                hold_run=hold_run,
                beam_lookup=beam_lookup,
                memory=memory,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("run_supervisor.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def run_supervisor_lifespan(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    hold_run: HoldRunHandler,
    beam_lookup: BeamAvailabilityLookup | None = None,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the RunSupervisor loop for the duration of the context.

    No-op unless `settings.run_supervisor_enabled` is True (default off, so a
    deployment opts in explicitly).
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
    _log.info("run_supervisor.started", interval_seconds=interval)
    task = asyncio.create_task(
        _supervise_loop(deps, list_runs, hold_run, lookup, interval),
        name="run-supervisor",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("run_supervisor.stopped")


__all__ = ["SupervisionOutcome", "decide_supervision", "run_supervisor_lifespan"]
