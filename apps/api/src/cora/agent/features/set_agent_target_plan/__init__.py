"""Vertical slice for the `SetAgentTargetPlan` command.

Sets (or clears) the recipe Plan an autonomous agent (the RunInitiator)
starts for each ready Subject. PUT-semantics: the supplied target_plan_id
IS the post-set target; None clears it.

Idempotent: setting the target to its current value emits NO event.

Source set is `{Defined, Versioned, Suspended}` (Deprecated is the only
blocking state, mirroring update_agent_budget). No cross-BC Plan-existence
check (eventual-consistency stance).
"""

from cora.agent.features.set_agent_target_plan import tool
from cora.agent.features.set_agent_target_plan.command import SetAgentTargetPlan
from cora.agent.features.set_agent_target_plan.decider import decide
from cora.agent.features.set_agent_target_plan.handler import Handler, bind
from cora.agent.features.set_agent_target_plan.route import router

__all__ = [
    "Handler",
    "SetAgentTargetPlan",
    "bind",
    "decide",
    "router",
    "tool",
]
