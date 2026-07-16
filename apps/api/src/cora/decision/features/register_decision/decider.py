"""Pure decider for the `RegisterDecision` command.

Pure function: given the (always None) Decision state, a
`RegisterDecision` command, and a pre-loaded
`DecisionRegistrationContext`, returns the events to append. No
I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Cross-aggregate validation (gate-review Q2 lock B)

Existence-only checks; the decider trusts the handler's loads.
The handler raises `DeciderActorNotFoundError` upstream if the
Actor doesn't exist (and `context.actor: Actor` is non-Optional
to make the contract explicit at the type boundary). The decider
checks only the parent-Decision branch because parent_id is
conditional:

  - If `command.parent_id` is set, `context.parent` must be
    non-None (handler raises `DecisionParentNotFoundError`
    upstream; this branch is the decider-level statement of the
    contract for the conditional case).

No status checks: a Decision can be made by any Actor including
Deactivated (the historical fact still holds), and any prior
Decision can be the parent in an override chain.

## Override-kind invariant (gate-review L15)

`override_kind` only makes sense with a `parent_id`. The decider
raises `OverrideKindRequiresParentError` if the command has
`override_kind` set but `parent_id` is None.

## Actor-kind invariant

`register_decision` is the operator-driven slice. Agent-emitted
Decisions go through the subscriber path (CautionDrafter,
RunDebriefer) so the Signer port can sign each row per
[[project_signed_events_design]].

The signing obligation is discriminated by EVENT TYPE, not by actor
kind. Every signing site gates on `signer is None or
new_event.event_type not in SIGNED_EVENT_TYPES` (=
{DecisionRegistered}); none of them reads `Actor.kind`, and
`tests/architecture/test_actor_kind_blindness.py` pins that.

The decider refuses `context.actor.kind == AGENT` with
`InvalidActorKindForDecisionError` so this slice does not offer an
unsigned path for rows that the subscriber path would have signed.
The guard reads the kind of the Actor a Decision is ATTRIBUTED to
(`command.decided_by`), never the authenticated principal, which the
Authorize port structurally cannot observe. Note the guard rests on
honest attribution: `decided_by` is body-supplied and is not
reconciled against `principal_id`.

## VO trim semantics

Field VOs (`DecisionChoice`, `DecisionContext`, `DecisionRule`)
handle their own trimming + validation in `__post_init__`. The
optional fields use top-level `validate_*` helpers because they
have no other invariants beyond shape.
"""

from datetime import datetime
from uuid import UUID

from cora.access.aggregates.actor import ActorKind
from cora.decision.aggregates.decision import (
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionContext,
    DecisionParentNotFoundError,
    DecisionRegistered,
    DecisionRule,
    validate_alternatives,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
    validate_reasoning_signature,
)
from cora.decision.errors import (
    InvalidActorKindForDecisionError,
    OverrideKindRequiresParentError,
)
from cora.decision.features.register_decision.command import RegisterDecision
from cora.decision.features.register_decision.context import DecisionRegistrationContext


def decide(
    state: Decision | None,
    command: RegisterDecision,
    *,
    context: DecisionRegistrationContext,
    now: datetime,
    new_id: UUID,
) -> list[DecisionRegistered]:
    """Decide the events produced by registering a new Decision.

    Invariants:
      - State must be None (genesis-only)
        -> DecisionAlreadyExistsError
      - Actor.kind must NOT be AGENT (Agent-emitted Decisions go
        through the signed subscriber path)
        -> InvalidActorKindForDecisionError
      - When parent_id is set, parent Decision must exist
        -> DecisionParentNotFoundError
      - override_kind requires a parent_id
        -> OverrideKindRequiresParentError
      - Choice must be valid -> InvalidDecisionChoiceError
        (via DecisionChoice VO)
      - Context must be valid -> InvalidDecisionContextError
        (via DecisionContext VO)
      - Rule (when set) must be valid -> InvalidDecisionRuleError
        (via DecisionRule VO)
      - Reasoning must be non-empty + within length bound
        -> InvalidDecisionReasoningError (via validate_reasoning)
      - Confidence (when set) must be in [0.0, 1.0]
        -> InvalidDecisionConfidenceError (via validate_confidence)
      - Alternatives must satisfy shape + cardinality
        -> InvalidDecisionAlternativesError (via validate_alternatives)
      - Inputs must satisfy shape -> InvalidDecisionInputsError
        (via validate_inputs)
      - reasoning_signature (when set) must be valid
        -> InvalidDecisionReasoningSignatureError
        (via validate_reasoning_signature)
    """
    if state is not None:
        raise DecisionAlreadyExistsError(state.id)

    if context.actor.kind == ActorKind.AGENT:
        raise InvalidActorKindForDecisionError("agent")

    # Cross-agg parent guard (handler raises DecisionParentNotFoundError
    # upstream; this branch is the decider-level statement of contract
    # for the conditional case).
    if command.parent_id is not None and context.parent is None:
        raise DecisionParentNotFoundError(command.parent_id)

    # override_kind / parent_id consistency.
    if command.override_kind is not None and command.parent_id is None:
        raise OverrideKindRequiresParentError(command.override_kind)

    # Field-level validation via VOs + helpers.
    choice = DecisionChoice(command.choice)
    decision_context = DecisionContext(command.context)
    rule = DecisionRule(command.rule) if command.rule is not None else None
    reasoning = validate_reasoning(command.reasoning)
    confidence = validate_confidence(command.confidence)
    alternatives = validate_alternatives(command.alternatives)
    inputs = validate_inputs(command.inputs)
    reasoning_signature = validate_reasoning_signature(command.reasoning_signature)

    return [
        DecisionRegistered(
            decision_id=new_id,
            decided_by=command.decided_by,
            context=decision_context.value,
            choice=choice.value,
            parent_id=command.parent_id,
            override_kind=command.override_kind,
            rule=rule.value if rule is not None else None,
            reasoning=reasoning,
            confidence=confidence,
            confidence_source=command.confidence_source,
            alternatives=alternatives,
            inputs=inputs,
            reasoning_signature=reasoning_signature,
            occurred_at=now,
        )
    ]
