"""ExperimentSteerer runtime seam: the agent that records ACROSS-procedure steering.

Hosted at the composition root (`cora.api`) for the same reason as
`_run_initiator` / `_run_supervisor`: it composes a Decision BC event AND will
issue Operation BC commands (a follow-on hold), and only `cora.api` may depend on
both BCs (sidestepping `test_no_cross_bc_features_imports`, which scans BC
packages, not the composition root).

## What it does (the seam, not the proactive loop)

The decide layer runs ONE steered Procedure autonomously
(`conduct_until_advised`), recording each iteration's advice on
`ProcedureIterationEnded`. The ExperimentSteerer is the L3 layer above that: it
owns a steered experiment ACROSS more than one Procedure, and records each
across-procedure disposition as one
`Decision(context=ExperimentSteering)` authored by the ExperimentSteerer agent.

`record_steering_decision` is that seam: given a procedure that just terminated
and the across-procedure choice (Continue / Conclude / Hold / ...), it composes,
signs, and appends one `DecisionRegistered`, returning the new `decision_id` so a
caller can thread it into a follow-on command's `decided_by_decision_id` (for a
Hold, the agent-issued `hold_procedure`). The provenance fields reuse the decide
layer's `AdviceAuditFields` so within-procedure (iteration ledger) and
across-procedure (this Decision) provenance share one mapping.

The proactive DRIVER loop (which Procedure next, when to Conclude, max-in-flight)
is a later slice; this entry point records ONE across-procedure decision and is
driven white-box by tests / a future loop.

## Why a callable, not a subscriber

The ExperimentSteerer is proactive: it acts BETWEEN steered Procedures, with no
natural trigger event to subscribe to (the reactive run_debriefer / caution_drafter
subscribe to terminal Run events; there is no "campaign should advance" event).
So this is a callable seam the future driver invokes, mirroring `_run_initiator`,
not a projection-wired subscriber.

## Authorization and signing (no bypass)

An Agent cannot use the operator-only `register_decision` slice (its decider
rejects `ActorKind.AGENT`). Agent Decisions go through this signed direct-append
path: compose `DecisionRegistered` from public Decision VOs, sign via the Signer
port (DecisionRegistered is in `SIGNED_EVENT_TYPES`, so an AI-agent row is signed
at write time per the design lock), and append. The runtime gates on
`Actor.active`, so deactivating the ExperimentSteerer Actor stands it down.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.seed_experiment_steerer import EXPERIMENT_STEERER_AGENT_ID
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_EXPERIMENT_STEERING,
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
from cora.infrastructure.signing import SIGNED_EVENT_TYPES
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.event_store import NewEvent
    from cora.infrastructure.ports.signer import Signer
    from cora.operation.ports.decide_port import AdviceAuditFields

_log = get_logger(__name__)

_RULE = "agent:ExperimentSteerer:v1"
_COMMAND_NAME = "ExperimentSteererTurn"
_STREAM_TYPE = "Decision"

# Stable namespace for deriving deterministic Decision ids from a
# (procedure_id, turn) pair. uuid5 keeps a retried record idempotent: a second
# append hits expected_version=0 on the existing stream and raises
# ConcurrencyError, which the seam treats as a no-op. Pinned forever; changing it
# invalidates every prior deterministic id.
_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-000057330002")


def _derive_decision_id(procedure_id: UUID, turn: int) -> UUID:
    """Deterministic Decision id from the steered procedure + the across-procedure turn."""
    return uuid5(_DECISION_NAMESPACE, f"{procedure_id}:{turn}")


async def _maybe_sign(signer: Signer | None, new_event: NewEvent, *, actor_id: UUID) -> NewEvent:
    """Attach a signature when a Signer is wired AND the event type must be signed.

    DecisionRegistered is in SIGNED_EVENT_TYPES, so an AI-agent row is signed at
    write time (the design lock's "AI-agent events signed" stance; an unsigned
    AGENT row would trip the strict audit sweep). No-op when no Signer is wired.
    Mirrors `RunDebrieferSubscriber._maybe_sign`.
    """
    if signer is None or new_event.event_type not in SIGNED_EVENT_TYPES:
        return new_event
    signature, kid, signing_version = await signer.sign(
        event_type=new_event.event_type,
        payload=new_event.payload,
        actor_id=actor_id,
    )
    return replace(
        new_event,
        signature=signature,
        signature_kid=kid,
        signature_version=signing_version,
    )


async def record_steering_decision(
    deps: Kernel,
    *,
    procedure_id: UUID,
    turn: int,
    choice: str,
    advice_audit: AdviceAuditFields,
) -> UUID | None:
    """Record one across-procedure steering Decision; return its id (None if stood down).

    Composes, signs, and appends one
    `Decision(context=ExperimentSteering, choice=<choice>)` authored by the
    ExperimentSteerer agent. `choice` is an `ExperimentSteeringChoice` value
    (Continue / Conclude / Hold / SteeringDeferred / SteeringConflicted).
    `advice_audit` is the decide layer's `AdviceAuditFields` (the same provenance
    that lands on the iteration ledger), mapped onto the Decision's
    reasoning / confidence / confidence_source / alternatives fields so the two
    audit homes never drift. `turn` is the 0-based across-procedure step, making
    the Decision id deterministic + retry-idempotent.

    Returns the `decision_id` so a caller can thread it into a follow-on command's
    `decided_by_decision_id` (for a Hold, the agent-issued `hold_procedure`).
    Returns None when the agent is not seeded / deactivated (a logged stand-down,
    no bypass), mirroring `_run_initiator`.
    """
    actor = await load_actor(deps.event_store, EXPERIMENT_STEERER_AGENT_ID)
    if actor is None or not actor.active:
        _log.info("experiment_steerer.stood_down", seeded=actor is not None)
        return None

    now = deps.clock.now()
    decision_id = _derive_decision_id(procedure_id, turn)
    inputs = validate_inputs(
        {
            "procedure_id": str(procedure_id),
            "turn": turn,
            "model_ref": advice_audit.model_ref if advice_audit.model_ref is not None else "None",
        }
    )
    domain_event = DecisionRegistered(
        decision_id=decision_id,
        decided_by=ActorId(EXPERIMENT_STEERER_AGENT_ID),
        context=DecisionContext(DECISION_CONTEXT_EXPERIMENT_STEERING).value,
        choice=DecisionChoice(choice).value,
        parent_id=None,
        override_kind=None,
        rule=DecisionRule(_RULE).value,
        reasoning=validate_reasoning(advice_audit.reasoning),
        confidence=validate_confidence(advice_audit.confidence),
        confidence_source=(
            advice_audit.confidence_source
            if advice_audit.confidence_source is not None
            else DecisionConfidenceSource.SELF_REPORTED
        ),
        alternatives=advice_audit.alternatives,
        inputs=inputs,
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
        principal_id=EXPERIMENT_STEERER_AGENT_ID,
    )
    new_event = await _maybe_sign(deps.signer, new_event, actor_id=EXPERIMENT_STEERER_AGENT_ID)
    try:
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=decision_id,
            expected_version=0,
            events=[new_event],
        )
    except ConcurrencyError:
        # Deterministic id + retry: the Decision is already recorded. Treat as a
        # no-op success and return the id so the caller can still link to it.
        _log.info("experiment_steerer.decision_already_written", decision_id=str(decision_id))
        return decision_id

    _log.info(
        "experiment_steerer.decision_recorded",
        decision_id=str(decision_id),
        procedure_id=str(procedure_id),
        turn=turn,
        choice=choice,
    )
    return decision_id


__all__ = ["record_steering_decision"]
