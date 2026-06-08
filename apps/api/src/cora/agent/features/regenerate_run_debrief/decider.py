"""Pure decider for the `regenerate_run_debrief` slice.

Composes the `DecisionRegistered` event for an on-demand RunDebriefer
invocation. Pure function: given the (always-None) Decision state, the
`RegenerateRunDebrief` command, and a handler-built
`RegenerateRunDebriefContext`, returns the event(s) to append. No I/O,
no awaits, no clock / id-generator calls.

Invariants:
  - State is always None (genesis event, fresh Decision stream).
  - `context.actor.active` is True (handler raised
    AgentDeactivatedError otherwise).
  - `command.parent_decision_id` (when set) points at a real Decision
    in the same Run AND with `context = "RunDebrief"` (handler raised
    DecisionParentNotFoundError / DecisionParentRunMismatchError /
    DecisionParentAgentMismatchError otherwise).
  - `context.choice` is a valid `DecisionChoice` string (open-string VO
    raises `InvalidDecisionChoiceError` otherwise).
  - `context.reasoning` is non-empty + within length bound
    (`validate_reasoning` raises otherwise).
  - `context.confidence` is in [0.0, 1.0] when not None
    (`validate_confidence` raises otherwise).

## Why a separate decider

The cross-BC slice-contract test
(`tests/architecture/test_slice_contract.py`) requires `decider.py`
for every command slice. The LLM-response-to-`DecisionRegistered`
mapping is genuinely pure and benefits from extraction: future
on-demand agent slices and a Pattern B subscriber would both consume
the same shape.

The Pattern A subscriber (`cora.agent.subscribers.run_debriefer`)
currently inlines an equivalent composition. Rule-of-three trigger
to hoist this decider out of the slice and into a shared module
fires when EITHER a second on-demand agent slice ships OR the
subscriber's composition is refactored to call through this decider.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.context import RegenerateRunDebriefContext
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    Decision,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    validate_confidence,
    validate_inputs,
    validate_reasoning,
)
from cora.shared.identity import ActorId

_DECISION_RULE = "agent:RunDebriefer:v1"


def decide(
    state: Decision | None,
    command: RegenerateRunDebrief,
    *,
    context: RegenerateRunDebriefContext,
    now: datetime,
    new_id: UUID,
) -> list[DecisionRegistered]:
    """Compose the on-demand RunDebriefer `DecisionRegistered` event.

    `state` is always None (fresh Decision stream; the handler doesn't
    load Decision state). Accepted as a parameter for canonical
    signature parity with every other create-style decider.

    `context.choice` is constrained at the projection layer (and by the
    LLM's structured output schema) to the closed 6-value set, but the
    Decision BC's open-string `DecisionChoice` VO is used here so the
    decider stays vocabulary-agnostic.

    `context.extra_inputs` merges into the base inputs after
    the base keys are set; collisions on `run_id` / `trigger` /
    `prompt_template_id` are silently overwritten by the extra dict
    (intentional: callers supplying these keys override on purpose,
    eg. the DebriefDeferred path's `failure_error_class`).
    """
    _ = state  # always None for genesis; signature parity only.
    decision_choice = DecisionChoice(context.choice)
    decision_context = DecisionContext(DECISION_CONTEXT_RUN_DEBRIEF)
    rule = DecisionRule(_DECISION_RULE)
    base_inputs: dict[str, Any] = {
        "run_id": str(command.run_id),
        "trigger": "on-demand",
        "prompt_template_id": str(RUN_DEBRIEF_PROMPT_TEMPLATE_ID),
    }
    if context.extra_inputs:
        base_inputs.update(context.extra_inputs)
    inputs = validate_inputs(base_inputs)
    validated_reasoning = validate_reasoning(context.reasoning)
    validated_confidence = validate_confidence(context.confidence)

    return [
        DecisionRegistered(
            decision_id=new_id,
            decided_by=ActorId(context.actor.id),
            context=decision_context.value,
            choice=decision_choice.value,
            parent_id=command.parent_decision_id,
            override_kind=None,
            rule=rule.value,
            reasoning=validated_reasoning,
            confidence=validated_confidence,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            inputs=inputs,
            reasoning_signature=None,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
