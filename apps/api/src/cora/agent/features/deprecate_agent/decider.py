"""Pure decider for the `DeprecateAgent` command.

Source set is `{Defined, Versioned, Suspended}` — `Suspended` is
in the set so an operator who paused an agent can still retire it
without resuming first. Strict-not-idempotent: re-
deprecating an already-Deprecated Agent raises
`AgentCannotDeprecateError`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Defined`, `Versioned`, or `Suspended` ->
    `AgentCannotDeprecateError`
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotDeprecateError,
    AgentDeprecated,
    AgentNotFoundError,
    AgentStatus,
)
from cora.agent.features.deprecate_agent.command import DeprecateAgent

_DEPRECATABLE_STATUSES: tuple[AgentStatus, ...] = (
    AgentStatus.DEFINED,
    AgentStatus.VERSIONED,
    AgentStatus.SUSPENDED,
)


def decide(
    state: Agent | None,
    command: DeprecateAgent,
    *,
    now: datetime,
) -> list[AgentDeprecated]:
    """Decide the events produced by deprecating an Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must be Defined, Versioned, or Suspended
        -> AgentCannotDeprecateError
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise AgentCannotDeprecateError(state.id, state.status)

    return [
        AgentDeprecated(
            agent_id=state.id,
            reason=command.reason.value,
            occurred_at=now,
        )
    ]
