"""Pure decider for the `RestateAgentDefinition` command.

Source set is `{Defined, Versioned, Suspended}`; Deprecated is the only
blocking state, mirroring update_agent_budget and update_agent_target_plan. A
terminal Agent's record is closed, and restating what a retired agent thinks
with says nothing anyone can act on.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated` -> `AgentCannotRestateDefinitionError`
  - At least one of name / brain must be supplied
    -> `InvalidAgentDefinitionRestatementError`
  - `reason` must be valid -> `InvalidAgentRestatementReasonError`
  - Idempotent: restating every supplied field to its current value returns []
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRestateDefinitionError,
    AgentDefinitionRestated,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    InvalidAgentDefinitionRestatementError,
    InvalidAgentRestatementReasonError,
)
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.text_bounds import REASON_MAX_LENGTH


def decide(
    state: Agent | None,
    command: RestateAgentDefinition,
    *,
    now: datetime,
) -> list[AgentDefinitionRestated]:
    """Decide the events produced by restating an Agent's definition.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Status must not be Deprecated -> AgentCannotRestateDefinitionError
      - At least one of name / brain -> InvalidAgentDefinitionRestatementError
      - Idempotent: nothing actually changes -> no event
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotRestateDefinitionError(state.id, state.status)
    if command.name is None and command.brain is None:
        raise InvalidAgentDefinitionRestatementError(state.id)

    reason = validate_bounded_text(
        command.reason,
        max_length=REASON_MAX_LENGTH,
        error_class=InvalidAgentRestatementReasonError,
    )

    # Validate the name through the same VO the genesis used, so a restatement
    # cannot introduce a name `define_agent` would have refused.
    name = AgentName(command.name) if command.name is not None else None

    # Idempotent on the SUPPLIED fields only. A command naming just the brain
    # must not be judged unchanged because the name it did not mention still
    # matches: that would make a partial restatement depend on a field the
    # caller said nothing about.
    name_unchanged = name is None or name == state.name
    brain_unchanged = command.brain is None or command.brain == state.brain
    if name_unchanged and brain_unchanged:
        return []

    return [
        AgentDefinitionRestated(
            agent_id=state.id,
            name=name.value if name is not None else None,
            brain=command.brain,
            reason=reason,
            occurred_at=now,
        )
    ]
