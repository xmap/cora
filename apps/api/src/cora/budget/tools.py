"""MCP tool registration for the budget BC.

`register_budget_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `BudgetHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.budget.features.activate_allocation import tool as activate_allocation_tool
from cora.budget.features.amend_allocation_ceiling import tool as amend_allocation_ceiling_tool
from cora.budget.features.grant_allocation import tool as grant_allocation_tool
from cora.budget.features.seal_allocation import tool as seal_allocation_tool
from cora.budget.features.void_allocation import tool as void_allocation_tool
from cora.budget.wire import BudgetHandlers


def register_budget_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], BudgetHandlers],
) -> None:
    """Register every budget slice's MCP tool on the FastMCP server."""
    grant_allocation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().grant_allocation,
    )
    activate_allocation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().activate_allocation,
    )
    amend_allocation_ceiling_tool.register(
        mcp,
        get_handler=lambda: get_handlers().amend_allocation_ceiling,
    )
    seal_allocation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().seal_allocation,
    )
    void_allocation_tool.register(
        mcp,
        get_handler=lambda: get_handlers().void_allocation,
    )
