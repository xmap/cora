"""RunInitiator runtime: the agent that autonomously STARTS Runs.

Hosted at the composition root (`cora.api`) for the same reason as
`_run_supervisor`: it issues a Run BC command AND composes a Decision BC
event, and only `cora.api` may depend on both BCs (so it sidesteps the
`test_no_cross_bc_features_imports` ban, which scans BC packages, not the
composition root).

## What it does

`initiate_run` is the authorized, attributed run-start seam (slice 1). Given
an eligible Plan (and optional Subject), it:

  1. records ONE Decision(context=RunInitiation, choice=Start) authored by
     the RunInitiator agent (the provenance of WHY this Run was started), and
  2. issues `start_run` as the agent principal through the SAME bound handler
     a human uses, attributed via `trigger_source="RunInitiator"` and linked
     to the Decision via `decided_by_decision_id`.

This is the run-start counterpart to the RunSupervisor's hold / resume: the
supervisor protects in-flight Runs (reactive); the initiator creates them
(proactive). The autonomous SELECTION loop (which Plan / Subject next,
cadence, max-in-flight) is a later slice; this entry point starts ONE
supplied eligible Run and is driven white-box by tests / a future loop.

## Authorization and safety (no bypass)

The start flows through the normal bound handler: the Authorize port gates
it (under TrustAuthorize the operator's Policy must grant this principal
StartRun), and the full start-safety envelope (Active clearance, supplies,
enclosures, beam) still gates every start regardless of actor kind. An
unauthorized start is a logged no-op (no Run created); safety-envelope
refusals propagate to the caller. The runtime gates on `Actor.active`, so
deactivating the RunInitiator Actor stands it down.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID
from cora.api._flag_watcher import WatcherReadUnauthorizedError, probe_read_grant
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_INITIATION,
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
from cora.run.errors import UnauthorizedError
from cora.run.features.list_runs import ListRuns
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.shared.identity import ActorId
from cora.subject.features.list_subjects import ListSubjects

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from typing import Any
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel
    from cora.run.features.list_runs import RunSummaryItem
    from cora.run.features.list_runs.handler import Handler as ListRunsHandler
    from cora.subject.features.list_subjects import SubjectSummaryItem
    from cora.subject.features.list_subjects.handler import Handler as ListSubjectsHandler

_log = get_logger(__name__)

_RULE = "agent:RunInitiator:v1"
_CHOICE_START = "Start"
_COMMAND_NAME = "RunInitiatorStart"
_TRIGGER_SOURCE = "RunInitiator"
_STREAM_TYPE = "Decision"

_REASONING = (
    "Autonomous acquisition: started the next eligible Run for the bound Plan "
    "through the authorized start path. The start-safety envelope gated the start."
)

_PAGE_LIMIT = 100
_READ_RUNS = "ListRuns"
_READ_SUBJECTS = "ListSubjects"


async def _record_initiation_decision(
    deps: Kernel,
    *,
    decision_id: UUID,
    plan_id: UUID,
    subject_id: UUID | None,
) -> None:
    """Compose and append one DecisionRegistered (Decision BC genesis).

    Mirrors `_run_supervisor._record_decision` (public Decision VOs only). The
    decision_id is a fresh random id on a brand-new stream, so a ConcurrencyError
    is unreachable today; the branch is retained for symmetry with the supervisor
    and as a guard should a future slice adopt a deterministic, retryable id.
    """
    now = deps.clock.now()
    decision_inputs = {
        "plan_id": str(plan_id),
        "subject_id": str(subject_id) if subject_id is not None else "None",
    }
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(RUN_INITIATOR_AGENT_ID),
        context=DecisionContext(DECISION_CONTEXT_RUN_INITIATION).value,
        choice=DecisionChoice(_CHOICE_START).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(_RULE).value,
        reasoning=validate_reasoning(_REASONING),
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
        principal_id=RUN_INITIATOR_AGENT_ID,
    )
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        _log.info("run_initiator.decision_already_written", decision_id=str(decision_id))


async def initiate_run(
    deps: Kernel,
    *,
    plan_id: UUID,
    subject_id: UUID | None,
    name: str,
    override_parameters: dict[str, Any] | None = None,
    raid: str | None = None,
    campaign_id: UUID | None = None,
) -> UUID | None:
    """Start a Run as the RunInitiator agent through the authorized path.

    Records the run-initiation Decision, then issues `start_run` as the agent
    principal linked to that Decision. Returns the new Run id, or None when the
    agent is not seeded / deactivated, or the start is unauthorized (a logged
    no-op, no bypass). Safety-envelope refusals propagate to the caller.

    The Decision is recorded BEFORE the start (the decided_by_decision_id link
    needs the id to exist first), mirroring the RunSupervisor. So a blocked
    start, whether unauthorized (caught here) or refused by the safety envelope
    (propagated), leaves the RunInitiation Decision as the standing audit record
    that the agent decided to start but was blocked, with no RunStarted.
    """
    actor = await load_actor(deps.event_store, RUN_INITIATOR_AGENT_ID)
    if actor is None or not actor.active:
        # Not seeded yet, or deactivated by an operator: stand down.
        _log.info("run_initiator.stood_down", seeded=actor is not None)
        return None

    decision_id = deps.id_generator.new_id()
    await _record_initiation_decision(
        deps, decision_id=decision_id, plan_id=plan_id, subject_id=subject_id
    )

    try:
        return await bind_start_run(deps)(
            StartRun(
                name=name,
                plan_id=plan_id,
                subject_id=subject_id,
                override_parameters=override_parameters or {},
                trigger_source=_TRIGGER_SOURCE,
                raid=raid,
                campaign_id=campaign_id,
                decided_by_decision_id=decision_id,
            ),
            principal_id=RUN_INITIATOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
    except UnauthorizedError:
        # Configuration fault: the initiator principal is not granted StartRun.
        # Log loudly; take no autonomous action, no bypass (the Decision stands
        # as the audit record that the agent decided but was blocked).
        _log.warning("run_initiator.start_unauthorized", plan_id=str(plan_id))
        return None


async def _drain_running_runs(list_runs: ListRunsHandler, deps: Kernel) -> list[RunSummaryItem]:
    """Page through list_runs for status=Running; return all rows."""
    items: list[RunSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_runs(
            ListRuns(status="Running", cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=RUN_INITIATOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


async def _drain_mounted_subjects(
    list_subjects: ListSubjectsHandler, deps: Kernel
) -> list[SubjectSummaryItem]:
    """Page through list_subjects for status=Mounted; return all rows (the
    projection is created_at-ordered, so the result is oldest-mounted-first)."""
    items: list[SubjectSummaryItem] = []
    cursor: str | None = None
    while True:
        page = await list_subjects(
            ListSubjects(status="Mounted", cursor=cursor, limit=_PAGE_LIMIT),
            principal_id=RUN_INITIATOR_AGENT_ID,
            correlation_id=deps.id_generator.new_id(),
            surface_id=NIL_SENTINEL_ID,
        )
        items.extend(page.items)
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


async def initiate_tick(
    *,
    deps: Kernel,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    plan_id: UUID,
    max_in_flight: int,
    started: set[UUID],
) -> list[UUID]:
    """One selection pass: start the next ready (Mounted) Subject(s) for `plan_id`,
    capped so at most `max_in_flight` Runs are in flight. Returns the Run ids
    started this tick.

    Serialization for one-stage hardware comes from the cap (default 1 in the
    standing loop): a Subject already covered by a Running Run, or already started
    this session (`started`, the in-process dedup memory mirroring RunSupervisor),
    is skipped. The `started` set covers the projection-lag window where a
    just-issued start is not yet visible as Running; the Running exclusion covers
    the steady state. Each start flows through `initiate_run`, so it is authorized,
    attributed, and Decision-linked exactly as a single agent start.

    A per-Subject StartRun denial makes `initiate_run` return None (a logged
    no-op); that Subject is not added to `started`, so a transient fault is
    retried next tick. `max_in_flight <= 0` makes the tick inert (returns []); the
    daemon that drives this on a cadence enforces a >= 1 floor on the setting.
    """
    actor = await load_actor(deps.event_store, RUN_INITIATOR_AGENT_ID)
    if actor is None or not actor.active:
        # Not seeded yet, or deactivated by an operator: stand down.
        _log.info("run_initiator.stood_down", seeded=actor is not None)
        return []

    try:
        running = await _drain_running_runs(list_runs, deps)
    except UnauthorizedError as err:
        raise WatcherReadUnauthorizedError(
            query_name=_READ_RUNS, principal_id=RUN_INITIATOR_AGENT_ID, reason=str(err)
        ) from err
    try:
        ready = await _drain_mounted_subjects(list_subjects, deps)
    except UnauthorizedError as err:
        raise WatcherReadUnauthorizedError(
            query_name=_READ_SUBJECTS, principal_id=RUN_INITIATOR_AGENT_ID, reason=str(err)
        ) from err

    slots = max_in_flight - len(running)
    if slots <= 0:
        return []

    running_subject_ids = {item.subject_id for item in running if item.subject_id is not None}
    started_run_ids: list[UUID] = []
    for subject in ready:
        if len(started_run_ids) >= slots:
            break
        if subject.subject_id in running_subject_ids or subject.subject_id in started:
            continue
        run_id = await initiate_run(
            deps,
            plan_id=plan_id,
            subject_id=subject.subject_id,
            name=f"Autonomous scan: {subject.name}",
        )
        if run_id is not None:
            started.add(subject.subject_id)
            started_run_ids.append(run_id)
    return started_run_ids


async def _initiate_loop(
    deps: Kernel,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    plan_id: UUID,
    max_in_flight: int,
    interval_seconds: float,
) -> None:
    """Periodic initiation loop. A failed tick is logged; the next tick retries.

    The `started` set is per-loop in-process dedup memory (resets on restart,
    same posture as the RunSupervisor's `memory`)."""
    started: set[UUID] = set()
    read_denied = False
    while True:
        try:
            await initiate_tick(
                deps=deps,
                list_runs=list_runs,
                list_subjects=list_subjects,
                plan_id=plan_id,
                max_in_flight=max_in_flight,
                started=started,
            )
            if read_denied:
                _log.info("run_initiator.read_authorized_recovered")
                read_denied = False
        except asyncio.CancelledError:
            raise
        except WatcherReadUnauthorizedError as err:
            # A missing ListRuns / ListSubjects grant blinds the initiator; surface
            # it loudly (edge-triggered, once per denial episode) rather than as a
            # generic tick failure. The drain stands down for the tick.
            if not read_denied:
                _log.warning(
                    "run_initiator.read_unauthorized",
                    query_name=err.query_name,
                    principal_id=str(err.principal_id),
                    reason=err.reason,
                )
                read_denied = True
        except Exception:
            _log.exception("run_initiator.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def run_initiator_lifespan(
    deps: Kernel,
    *,
    list_runs: ListRunsHandler,
    list_subjects: ListSubjectsHandler,
    interval_seconds: float | None = None,
) -> AsyncGenerator[None]:
    """Spawn the RunInitiator loop for the duration of the context.

    No-op unless `settings.run_initiator_enabled` is True AND
    `settings.run_initiator_plan_id` is set (the recipe Plan the loop starts for
    each ready Subject); both default off / None so a deployment opts in
    explicitly. Mirrors `run_supervisor_lifespan`.
    """
    if not deps.settings.run_initiator_enabled:
        _log.info("run_initiator.skipped", reason="disabled")
        yield
        return

    plan_id = deps.settings.run_initiator_plan_id
    if plan_id is None:
        # Enabled but no recipe configured: inert, not a crash.
        _log.info("run_initiator.skipped", reason="no_plan_configured")
        yield
        return

    # The tick reads both ListRuns and ListSubjects; probe each grant at boot so a
    # missing one is surfaced loudly (or refuses boot in strict mode) rather than
    # silently blinding the loop.
    await probe_read_grant(
        deps,
        agent_id=RUN_INITIATOR_AGENT_ID,
        read_command=_READ_RUNS,
        log_prefix="run_initiator",
        strict=deps.settings.watcher_authz_strict,
    )
    await probe_read_grant(
        deps,
        agent_id=RUN_INITIATOR_AGENT_ID,
        read_command=_READ_SUBJECTS,
        log_prefix="run_initiator",
        strict=deps.settings.watcher_authz_strict,
    )

    interval = (
        interval_seconds
        if interval_seconds is not None
        else deps.settings.run_initiator_tick_seconds
    )
    max_in_flight = deps.settings.run_initiator_max_in_flight
    _log.info(
        "run_initiator.started",
        interval_seconds=interval,
        max_in_flight=max_in_flight,
        plan_id=str(plan_id),
    )
    task = asyncio.create_task(
        _initiate_loop(deps, list_runs, list_subjects, plan_id, max_in_flight, interval),
        name="run-initiator",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("run_initiator.stopped")


__all__ = [
    "initiate_run",
    "initiate_tick",
    "run_initiator_lifespan",
]
