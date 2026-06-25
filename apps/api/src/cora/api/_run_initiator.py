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

from typing import TYPE_CHECKING
from uuid import uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_run_initiator import RUN_INITIATOR_AGENT_ID
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
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from typing import Any
    from uuid import UUID

    from cora.infrastructure.kernel import Kernel

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


__all__ = [
    "initiate_run",
]
