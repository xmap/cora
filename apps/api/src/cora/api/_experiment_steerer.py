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

from dataclasses import dataclass, replace
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
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.infrastructure.signing import SIGNED_EVENT_TYPES
from cora.operation.features.conduct_until_advised import ConductUntilAdvised
from cora.operation.features.hold_procedure import HoldProcedure
from cora.operation.ports.decide_port import AdviceAuditFields, objective_is_satisfied
from cora.shared.identity import ActorId

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports.event_store import NewEvent
    from cora.infrastructure.ports.signer import Signer
    from cora.operation.adapters.decide_port_config import DecidePortConfig
    from cora.operation.features.conduct_until_advised import (
        ConductUntilAdvisedResult,
    )
    from cora.operation.features.conduct_until_advised import Handler as ConductHandler
    from cora.operation.features.hold_procedure import Handler as HoldHandler
    from cora.operation.ports.decide_port import (
        SteeringBudget,
        SteeringObjective,
        SteeringSpace,
    )

_log = get_logger(__name__)

_RULE = "agent:ExperimentSteerer:v1"

# Across-procedure dispositions (ExperimentSteeringChoice values). v1 is a
# deterministic rule, the corpus's "first minimal slice" stand-in for the
# optimizer-DERIVED selection that is the end state (see steer_experiment).
_CHOICE_CONTINUE = "Continue"
_CHOICE_CONCLUDE = "Conclude"
_CHOICE_HOLD = "Hold"
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
    decision_id: UUID | None = None,
) -> UUID | None:
    """Record one across-procedure steering Decision; return its id (None if stood down).

    Composes, signs, and appends one
    `Decision(context=ExperimentSteering, choice=<choice>)` authored by the
    ExperimentSteerer agent. `choice` is an `ExperimentSteeringChoice` value
    (Continue / Conclude / Hold / SteeringDeferred / SteeringConflicted).
    `advice_audit` is the decide layer's `AdviceAuditFields` (the same provenance
    that lands on the iteration ledger), mapped onto the Decision's
    reasoning / confidence / confidence_source / alternatives fields so the two
    audit homes never drift. `turn` is the 0-based across-procedure step recorded
    on the Decision inputs.

    `decision_id` lets the caller supply the id. When omitted it is derived
    deterministically from `(procedure_id, turn)` (retry-idempotent for a caller
    whose `(procedure_id, turn)` pair is globally unique). The `steer_experiment`
    driver supplies a FRESH id per turn instead, because its `turn` is a
    call-local list index (not globally unique): a deterministic id keyed on a
    reused `procedure_id` at the same index could otherwise return a prior turn's
    Decision and link a follow-on Hold to the wrong choice. Mirrors
    `_run_initiator`'s fresh-id choice.

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
    if decision_id is None:
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


@dataclass(frozen=True)
class SteerExperimentStepResult:
    """One across-procedure turn's outcome: the procedure steered, the disposition
    chosen, the recorded Decision id (None if the agent stood down), and the
    underlying conduct result for the caller to inspect."""

    turn: int
    procedure_id: UUID
    choice: str
    decision_id: UUID | None
    conduct: ConductUntilAdvisedResult


def _across_procedure_choice(
    result: ConductUntilAdvisedResult, objective: SteeringObjective
) -> str:
    """The v1 deterministic across-procedure disposition for one steered procedure.

    Stand-in for the optimizer-DERIVED selection that is the end state:
      - a faulted steered procedure -> Hold (pause the campaign for the operator;
        the within-procedure fault is already on the iteration ledger).
      - objective met by the final measurements -> Conclude (the campaign goal is
        reached; stop steering further procedures).
      - otherwise -> Continue (steer the next procedure).
    """
    if not result.succeeded:
        return _CHOICE_HOLD
    if objective_is_satisfied(objective, result.measurements):
        return _CHOICE_CONCLUDE
    return _CHOICE_CONTINUE


async def steer_experiment(
    deps: Kernel,
    *,
    conduct: ConductHandler,
    hold_procedure: HoldHandler,
    procedure_ids: Sequence[UUID],
    objective: SteeringObjective,
    space: SteeringSpace,
    objective_capture_name: str,
    decide: DecidePortConfig,
    principal_id: UUID,
    correlation_id: UUID,
    budget: SteeringBudget | None = None,
) -> list[SteerExperimentStepResult]:
    """Drive the ExperimentSteerer across a sequence of steered procedures.

    The proactive across-procedure loop the 2a seam was built for. For each
    procedure in `procedure_ids` (the 0-based across-procedure `turn`):

      1. steer it: call the `conduct_until_advised` handler (one within-procedure
         measure-then-advise loop; the handler owns recipe re-expansion + brain
         construction from `decide` + authz).
      2. decide the across-procedure disposition by the v1 deterministic rule
         (`_across_procedure_choice`): Continue / Conclude / Hold.
      3. record it as one signed across-procedure Decision via the 2a seam
         (`record_steering_decision`), deterministic id keyed on (procedure_id, turn).
      4. on Hold, issue an agent-issued `hold_procedure` linked to that Decision
         via `decided_by_decision_id`.
      5. stop the across-loop on Conclude or Hold; else continue to the next
         procedure until `procedure_ids` is exhausted (the budget/exhaustion stop).

    Stands down (records nothing, returns the steps taken so far) if the agent is
    unseeded / deactivated: `record_steering_decision` returns None, which the
    loop treats as stand-down and stops.

    WHITE-BOX CALLABLE, not a standing daemon: the daemon + the per-campaign
    config home are the next increment. This is the minimal corpus-blessed first
    slice. THE END STATE (per the autonomous-experimentation corpus: Ax / Optuna /
    gpCAM / Ray Tune) is across-procedure SELECTION that is optimizer-DERIVED via
    ask/tell over campaign-level Decisions, with the Campaign aggregate promoted
    from a passive run-id envelope to the persistent owner of generation state
    (the Ax Experiment / GenerationStrategy / Orchestrator split is the reference).
    v1's deterministic Continue/Conclude/Hold rule + caller-supplied procedure_ids
    are the first step, not the destination.
    """
    results: list[SteerExperimentStepResult] = []
    for turn, procedure_id in enumerate(procedure_ids):
        conduct_result = await conduct(
            ConductUntilAdvised(
                procedure_id=procedure_id,
                objective=objective,
                space=space,
                objective_capture_name=objective_capture_name,
                decide=decide,
                budget=budget,
            ),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
        choice = _across_procedure_choice(conduct_result, objective)
        advice_audit = AdviceAuditFields(
            reasoning=_reasoning_for(choice),
            confidence=None,
            confidence_source=None,
            alternatives=(),
            model_ref=_RULE,
        )
        decision_id = await record_steering_decision(
            deps,
            procedure_id=procedure_id,
            turn=turn,
            choice=choice,
            advice_audit=advice_audit,
            # Fresh id per turn: this driver's `turn` is a call-local list index,
            # not globally unique, so a deterministic (procedure_id, turn) id could
            # collide across calls and link a Hold to a prior turn's Decision.
            decision_id=deps.id_generator.new_id(),
        )
        results.append(
            SteerExperimentStepResult(
                turn=turn,
                procedure_id=procedure_id,
                choice=choice,
                decision_id=decision_id,
                conduct=conduct_result,
            )
        )
        if decision_id is None:
            # Stand-down: the agent is unseeded / deactivated. Record nothing
            # further, take no follow-on action, stop the loop (no bypass).
            _log.info("experiment_steerer.stood_down_mid_loop", turn=turn)
            break
        if choice == _CHOICE_HOLD:
            await hold_procedure(
                HoldProcedure(
                    procedure_id=procedure_id,
                    reason="ExperimentSteerer paused the campaign after a faulted procedure",
                    decided_by_decision_id=decision_id,
                ),
                principal_id=EXPERIMENT_STEERER_AGENT_ID,
                correlation_id=correlation_id,
                surface_id=NIL_SENTINEL_ID,
            )
            break
        if choice == _CHOICE_CONCLUDE:
            break
    return results


def _reasoning_for(choice: str) -> str:
    """The deterministic across-procedure rationale recorded on the Decision."""
    if choice == _CHOICE_HOLD:
        return "Steered procedure faulted; paused the campaign for operator review."
    if choice == _CHOICE_CONCLUDE:
        return "Campaign objective met by the steered procedure; concluded the campaign."
    return "Campaign objective not yet met; steering the next procedure."


__all__ = ["SteerExperimentStepResult", "record_steering_decision", "steer_experiment"]
