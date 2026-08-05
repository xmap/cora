"""MCP tool registration for the Access BC.

`register_access_tools(mcp, *, get_handlers)` registers each slice's MCP
tool on the shared FastMCP server. `get_handlers` is a callable returning
the `AccessHandlers` bundle wired during the FastAPI lifespan; it's
invoked per tool call so the latest wiring is always used.

Cross-BC pattern: each BC exports `register_<bc>_tools(mcp, *, get_handlers)`.
The api entrypoint instantiates one FastMCP server, calls every BC's
registrar, then mounts the server at `/mcp`.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.access.features.deactivate_actor import tool as deactivate_actor_tool
from cora.access.features.forget_actor import tool as forget_actor_tool
from cora.access.features.get_actor import tool as get_actor_tool
from cora.access.features.list_actors import tool as list_actors_tool
from cora.access.features.reactivate_actor import tool as reactivate_actor_tool
from cora.access.features.register_actor import tool as register_actor_tool
from cora.access.wire import AccessHandlers


def register_access_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], AccessHandlers],
) -> None:
    """Register every Access slice's MCP tool on the FastMCP server."""
    register_actor_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_actor,
    )
    deactivate_actor_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deactivate_actor,
    )
    reactivate_actor_tool.register(
        mcp,
        get_handler=lambda: get_handlers().reactivate_actor,
    )
    forget_actor_tool.register(
        mcp,
        get_handler=lambda: get_handlers().forget_actor,
    )
    get_actor_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_actor,
    )
    list_actors_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_actors,
    )
