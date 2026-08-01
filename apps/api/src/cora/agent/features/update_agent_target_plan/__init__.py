"""Vertical slice for the `UpdateAgentTargetPlan` command.

Updates (or clears) the recipe Plan an autonomous agent (the RunInitiator)
starts for each ready Subject. PUT-semantics: the supplied target_plan_id
IS the post-update target; None clears it.

Idempotent: updating to the target to its current value emits NO event.

Source set is `{Defined, Versioned, Suspended}` (Deprecated is the only
blocking state, mirroring update_agent_budget). No cross-BC Plan-existence
check (eventual-consistency stance).
"""

from cora.agent.features.update_agent_target_plan import tool
from cora.agent.features.update_agent_target_plan.command import UpdateAgentTargetPlan
from cora.agent.features.update_agent_target_plan.decider import decide
from cora.agent.features.update_agent_target_plan.handler import Handler, bind
from cora.agent.features.update_agent_target_plan.route import router

__all__ = [
    "Handler",
    "UpdateAgentTargetPlan",
    "bind",
    "decide",
    "router",
    "tool",
]
