"""MCP tool registration for the Agent BC.

`register_agent_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `AgentHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.agent.features.announce_language_model_retirement import (
    tool as announce_language_model_retirement_tool,
)
from cora.agent.features.approve_language_model import tool as approve_language_model_tool
from cora.agent.features.define_agent import tool as define_agent_tool
from cora.agent.features.define_language_model import tool as define_language_model_tool
from cora.agent.features.deprecate_agent import tool as deprecate_agent_tool
from cora.agent.features.deprecate_language_model import tool as deprecate_language_model_tool
from cora.agent.features.dismiss_event_in_reaction import (
    tool as dismiss_event_in_reaction_tool,
)
from cora.agent.features.get_agent import tool as get_agent_tool
from cora.agent.features.grant_tool_to_agent import tool as grant_tool_to_agent_tool
from cora.agent.features.list_at_risk_results import tool as list_at_risk_results_tool
from cora.agent.features.promote_caution_proposal import tool as promote_caution_proposal_tool
from cora.agent.features.regenerate_run_debrief import tool as regenerate_run_debrief_tool
from cora.agent.features.regenerate_run_debrief.handler import (
    IdempotentHandler as RegenerateRunDebriefHandler,
)
from cora.agent.features.resume_agent import tool as resume_agent_tool
from cora.agent.features.retire_language_model import tool as retire_language_model_tool
from cora.agent.features.revoke_tool_from_agent import tool as revoke_tool_from_agent_tool
from cora.agent.features.suspend_agent import tool as suspend_agent_tool
from cora.agent.features.update_agent_budget import tool as update_agent_budget_tool
from cora.agent.features.update_agent_target_plan import tool as update_agent_target_plan_tool
from cora.agent.features.version_agent import tool as version_agent_tool
from cora.agent.wire import AgentHandlers


def register_agent_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], AgentHandlers],
) -> None:
    """Register every Agent slice's MCP tool on the FastMCP server."""
    define_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_agent,
    )
    version_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_agent,
    )
    deprecate_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_agent,
    )
    suspend_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().suspend_agent,
    )
    resume_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().resume_agent,
    )
    grant_tool_to_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().grant_tool_to_agent,
    )
    revoke_tool_from_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().revoke_tool_from_agent,
    )
    update_agent_budget_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_agent_budget,
    )
    update_agent_target_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().update_agent_target_plan,
    )
    get_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_agent,
    )
    # operator-triggered cross-BC promotion.
    promote_caution_proposal_tool.register(
        mcp,
        get_handler=lambda: get_handlers().promote_caution_proposal,
    )
    # regenerate_run_debrief handler is Optional in the bundle
    # (None when kernel.llm is unwired). The tool's lambda dereferences
    # at call time and raises a RuntimeError to surface as MCP isError;
    # this matches the REST 503 semantics. Deploys reach the None branch
    # whenever LLM_ENABLED is off (the default) or the key is unset.
    regenerate_run_debrief_tool.register(
        mcp,
        get_handler=lambda: _resolve_regenerate_run_debrief(get_handlers()),
    )
    dismiss_event_in_reaction_tool.register(
        mcp,
        get_handler=lambda: get_handlers().dismiss_event_in_reaction,
    )
    define_language_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_language_model,
    )
    approve_language_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().approve_language_model,
    )
    announce_language_model_retirement_tool.register(
        mcp,
        get_handler=lambda: get_handlers().announce_language_model_retirement,
    )
    retire_language_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().retire_language_model,
    )
    deprecate_language_model_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_language_model,
    )
    list_at_risk_results_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_at_risk_results,
    )


def _resolve_regenerate_run_debrief(handlers: AgentHandlers) -> RegenerateRunDebriefHandler:
    """Dereference the Optional regenerate_run_debrief handler with a loud
    failure when unwired. Mirrors the REST route's 503 path."""
    if handlers.regenerate_run_debrief is None:
        # Names BOTH settings rather than deriving which one applies:
        # this resolver has no Settings in scope (the tool registry is
        # wired from handlers alone), and threading one through to word a
        # message would widen the registration signature. The REST 503,
        # which does have Settings, names the specific one.
        msg = (
            "regenerate_run_debrief is unavailable: kernel.llm is not wired. "
            "It requires BOTH LLM_ENABLED=true (default false) and "
            "ANTHROPIC_API_KEY."
        )
        raise RuntimeError(msg)
    return handlers.regenerate_run_debrief
