"""Pure decider for the `RevokeToolFromAgent` command.

Source set is `{Defined, Versioned, Suspended}`. Idempotent: a
revoke of a tool not currently granted returns `[]` (no event).

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated` -> `AgentCannotRevokeToolError`
  - `tool_name` wrapped via `ToolName(...)`; 1-100 chars after trim
    -> `InvalidToolNameError`
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRevokeToolError,
    AgentNotFoundError,
    AgentStatus,
    AgentToolRevoked,
    ToolName,
)
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent


def decide(
    state: Agent | None,
    command: RevokeToolFromAgent,
    *,
    now: datetime,
) -> list[AgentToolRevoked]:
    """Decide the events produced by revoking a tool from an Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must not be Deprecated
        -> AgentCannotRevokeToolError
      - Tool name must be valid -> InvalidToolNameError
        (via ToolName VO)
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotRevokeToolError(state.id, state.status)

    tool_name = ToolName(command.tool_name)

    if tool_name not in state.tools:
        return []

    return [
        AgentToolRevoked(
            agent_id=state.id,
            tool_name=tool_name.value,
            reason=command.reason,
            occurred_at=now,
        )
    ]
