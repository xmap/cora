"""Pure decider for the `SetAgentTargetPlan` command.

PUT-semantics: the supplied `target_plan_id` IS the post-set target.
Source set is `{Defined, Versioned, Suspended}` (Deprecated is the only
blocking state, mirroring update_agent_budget). Idempotent: setting the
target to its current value returns `[]`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated`
    -> `AgentCannotSetTargetPlanError`
  - No cross-BC Plan-existence check (eventual-consistency stance).
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotSetTargetPlanError,
    AgentNotFoundError,
    AgentStatus,
    AgentTargetPlanSet,
)
from cora.agent.features.set_agent_target_plan.command import SetAgentTargetPlan


def decide(
    state: Agent | None,
    command: SetAgentTargetPlan,
    *,
    now: datetime,
) -> list[AgentTargetPlanSet]:
    """Decide the events produced by setting an Agent's target Plan.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must not be Deprecated -> AgentCannotSetTargetPlanError
      - Idempotent: target unchanged -> no event
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotSetTargetPlanError(state.id, state.status)

    if command.target_plan_id == state.target_plan_id:
        return []

    return [
        AgentTargetPlanSet(
            agent_id=state.id,
            target_plan_id=command.target_plan_id,
            occurred_at=now,
        )
    ]
