"""Vertical slice for the `UpdateAgentBudget` command.

Updates the Agent's declarative budget caps. Both
`monthly_usd_cap` and `daily_token_cap` are independently
nullable so the same command carries "set both", "set one,
clear the other", "set new monthly, keep daily", and "clear
all" cases. When both fields are None the Agent's `budget`
field is set to None.

Idempotent: a update that produces the same effective budget
as the current one emits NO event.

Source set is `{Defined, Versioned, Suspended}` (Deprecated is
the only blocking state; operators can fix budget while paused).

Enforcement is deferred to Budget BC adoption: today these are
declaration-only fields.
"""

from cora.agent.features.update_agent_budget import tool
from cora.agent.features.update_agent_budget.command import UpdateAgentBudget
from cora.agent.features.update_agent_budget.decider import decide
from cora.agent.features.update_agent_budget.handler import Handler, bind
from cora.agent.features.update_agent_budget.route import router

__all__ = [
    "Handler",
    "UpdateAgentBudget",
    "bind",
    "decide",
    "router",
    "tool",
]
