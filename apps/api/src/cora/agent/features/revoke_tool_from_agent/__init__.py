"""Vertical slice for the `RevokeToolFromAgent` command.

Removes one MCP tool from the Agent's declared tool set. Recorded
only: the set is metadata today, NOT consulted at invocation (see
`ToolName`), so revoking removes recorded intent, not an enforced
capability, and changes no runtime behavior. Idempotent: revoking a
tool the Agent doesn't have emits NO event. Source set is
`{Defined, Versioned, Suspended}` (Deprecated is the only blocking
state).
"""

from cora.agent.features.revoke_tool_from_agent import tool
from cora.agent.features.revoke_tool_from_agent.command import RevokeToolFromAgent
from cora.agent.features.revoke_tool_from_agent.decider import decide
from cora.agent.features.revoke_tool_from_agent.handler import Handler, bind
from cora.agent.features.revoke_tool_from_agent.route import router

__all__ = [
    "Handler",
    "RevokeToolFromAgent",
    "bind",
    "decide",
    "router",
    "tool",
]
