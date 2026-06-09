"""MCP tool registration for the Enclosure BC.

`register_enclosure_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the BC's handlers bundle wired during the
FastAPI lifespan; it is invoked per tool call so the latest wiring
is always used.

This sub-slice scaffolds the BC root without any slices wired; the
body is intentionally empty until later sub-slices land
`register_enclosure`, `observe_enclosure_permit`, and
`decommission_enclosure` per [[project_enclosure_stage1_design]].
The `get_handlers` return type is `object` at this sub-slice; it
narrows to `EnclosureHandlers` when `wire.py` lands at a later sub-slice.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP


def register_enclosure_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], object],
) -> None:
    """Register every Enclosure slice's MCP tool on the FastMCP server."""
    _ = mcp
    _ = get_handlers
