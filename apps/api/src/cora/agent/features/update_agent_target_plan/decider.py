"""Pure decider for the `UpdateAgentTargetPlan` command.

PUT-semantics: the supplied `target_plan_id` IS the post-update target.
Source set is `{Defined, Versioned, Suspended}` (Deprecated is the only
blocking state, mirroring update_agent_budget). Idempotent: updating to the
target to its current value returns `[]`.

## Validation

  - State must not be None -> `AgentNotFoundError`
  - Current status must not be `Deprecated`
    -> `AgentCannotUpdateTargetPlanError`
  - No cross-BC Plan-existence check (eventual-consistency stance).
"""

from datetime import datetime

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotUpdateTargetPlanError,
    AgentNotFoundError,
    AgentStatus,
    AgentTargetPlanUpdated,
)
from cora.agent.features.update_agent_target_plan.command import UpdateAgentTargetPlan


def decide(
    state: Agent | None,
    command: UpdateAgentTargetPlan,
    *,
    now: datetime,
) -> list[AgentTargetPlanUpdated]:
    """Decide the events produced by updating an Agent's target Plan.

    Invariants:
      - State must not be None -> AgentNotFoundError
      - Current status must not be Deprecated -> AgentCannotUpdateTargetPlanError
      - Idempotent: target unchanged -> no event
    """
    if state is None:
        raise AgentNotFoundError(command.agent_id)
    if state.status is AgentStatus.DEPRECATED:
        raise AgentCannotUpdateTargetPlanError(state.id, state.status)

    if command.target_plan_id == state.target_plan_id:
        return []

    return [
        AgentTargetPlanUpdated(
            agent_id=state.id,
            target_plan_id=command.target_plan_id,
            occurred_at=now,
        )
    ]
