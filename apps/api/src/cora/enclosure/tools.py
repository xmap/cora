"""MCP tool registration for the Enclosure BC.

`register_enclosure_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `EnclosureHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.enclosure.features.decommission_enclosure import tool as decommission_enclosure_tool
from cora.enclosure.features.observe_enclosure_status import tool as observe_enclosure_status_tool
from cora.enclosure.features.register_enclosure import tool as register_enclosure_tool
from cora.enclosure.wire import EnclosureHandlers


def register_enclosure_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], EnclosureHandlers],
) -> None:
    """Register every Enclosure slice's MCP tool on the FastMCP server."""
    register_enclosure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_enclosure,
    )
    # Stub registration for the in-process-only observe slice. The tool
    # module's register() is a no-op by design; this invocation satisfies
    # the tools-completeness architecture fitness without exposing a
    # public MCP tool surface.
    observe_enclosure_status_tool.register(
        mcp,
        get_handler=lambda: get_handlers().observe_enclosure_status,
    )
    decommission_enclosure_tool.register(
        mcp,
        get_handler=lambda: get_handlers().decommission_enclosure,
    )
