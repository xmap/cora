"""MCP tool registration for the Run BC.

`register_run_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `RunHandlers` bundle wired during the FastAPI lifespan;
it's invoked per tool call so the latest wiring is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.run.features.abort_run import tool as abort_run_tool
from cora.run.features.adjust_run import tool as adjust_run_tool
from cora.run.features.append_observations import tool as append_observations_tool
from cora.run.features.complete_run import tool as complete_run_tool
from cora.run.features.get_run import tool as get_run_tool
from cora.run.features.get_run_history import tool as get_run_history_tool
from cora.run.features.hold_run import tool as hold_run_tool
from cora.run.features.list_runs import tool as list_runs_tool
from cora.run.features.record_witnessed_run import tool as record_witnessed_run_tool
from cora.run.features.record_witnessed_run_outcome import (
    tool as record_witnessed_run_outcome_tool,
)
from cora.run.features.resume_run import tool as resume_run_tool
from cora.run.features.start_run import tool as start_run_tool
from cora.run.features.stop_run import tool as stop_run_tool
from cora.run.features.truncate_run import tool as truncate_run_tool
from cora.run.wire import RunHandlers


def register_run_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], RunHandlers],
) -> None:
    """Register every Run slice's MCP tool on the FastMCP server."""
    start_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_run,
    )
    # Stub registration for the in-process-only witnessed-genesis slice.
    # The tool module's register() is a no-op by design; this invocation
    # satisfies the tools-completeness architecture fitness without
    # exposing a public MCP tool surface.
    record_witnessed_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().record_witnessed_run,
    )
    # Stub registration for the in-process-only witnessed-terminal slice;
    # same rationale as record_witnessed_run above.
    record_witnessed_run_outcome_tool.register(
        mcp,
        get_handler=lambda: get_handlers().record_witnessed_run_outcome,
    )
    complete_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().complete_run,
    )
    abort_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().abort_run,
    )
    hold_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().hold_run,
    )
    resume_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().resume_run,
    )
    stop_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().stop_run,
    )
    truncate_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().truncate_run,
    )
    adjust_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().adjust_run,
    )
    append_observations_tool.register(
        mcp,
        get_handler=lambda: get_handlers().append_observations,
    )
    get_run_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_run,
    )
    get_run_history_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_run_history,
    )
    list_runs_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_runs,
    )
