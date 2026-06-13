"""MCP tool registration for the Operation BC.

`register_operation_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `OperationHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.operation.features.abort_procedure import tool as abort_procedure_tool
from cora.operation.features.append_activities import tool as append_activities_tool
from cora.operation.features.complete_procedure import tool as complete_procedure_tool
from cora.operation.features.conduct_procedure import tool as conduct_procedure_tool
from cora.operation.features.end_iteration import tool as end_iteration_tool
from cora.operation.features.get_procedure import tool as get_procedure_tool
from cora.operation.features.list_procedure_iterations import (
    tool as list_procedure_iterations_tool,
)
from cora.operation.features.list_procedures import tool as list_procedures_tool
from cora.operation.features.register_procedure import tool as register_procedure_tool
from cora.operation.features.register_procedure_from_recipe import (
    tool as register_procedure_from_recipe_tool,
)
from cora.operation.features.start_iteration import tool as start_iteration_tool
from cora.operation.features.start_procedure import tool as start_procedure_tool
from cora.operation.features.truncate_procedure import tool as truncate_procedure_tool
from cora.operation.wire import OperationHandlers


def register_operation_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], OperationHandlers],
) -> None:
    """Register every Operation slice's MCP tool on the FastMCP server."""
    register_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_procedure,
    )
    register_procedure_from_recipe_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_procedure_from_recipe,
    )
    start_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_procedure,
    )
    complete_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().complete_procedure,
    )
    abort_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().abort_procedure,
    )
    truncate_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().truncate_procedure,
    )
    start_iteration_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_iteration,
    )
    end_iteration_tool.register(
        mcp,
        get_handler=lambda: get_handlers().end_iteration,
    )
    append_activities_tool.register(
        mcp,
        get_handler=lambda: get_handlers().append_activities,
    )
    get_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_procedure,
    )
    list_procedures_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_procedures,
    )
    list_procedure_iterations_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_procedure_iterations,
    )
    conduct_procedure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().conduct_procedure,
    )
