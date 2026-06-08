"""Pure decider for the `ResumeAgent` command.

Source set is `{Suspended}` only. Strict-not-idempotent: resuming
a `Versioned` / `Defined` / `Deprecated` Agent raises
`AgentCannotResumeError`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must be `Suspended` -> `AgentCannotResumeError`

`resumed_by` is handler-injected from the request envelope's
`principal_id` (not on the command). The command surface omits the
field so callers cannot spoof a different resuming actor; the
fold-symmetry attribution half then lands on both the event payload
and Agent aggregate state per [[project_fold_symmetry_design]].
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotResumeError,
    AgentNotFoundError,
    AgentResumed,
    AgentStatus,
)
from cora.agent.features.resume_agent.command import ResumeAgent
from cora.shared.identity import ActorId


def decide(
    state: Agent | None,
    command: ResumeAgent,
    *,
    now: datetime,
    resumed_by: ActorId,
) -> list[AgentResumed]:
    """Decide the events produced by resuming an Agent.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must be Suspended -> AgentCannotResumeError
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is not AgentStatus.SUSPENDED:
        raise AgentCannotResumeError(state.id, state.status)

    return [
        AgentResumed(
            agent_id=state.id,
            resumed_by=resumed_by,
            occurred_at=now,
        )
    ]
