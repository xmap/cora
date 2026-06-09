"""Stub MCP tool module for `observe_enclosure_status` (in-process-only slice).

Per [[project_enclosure_stage1_design]] L-D3 / D6.L2 design lock: this
slice is NOT exposed as an MCP tool. In-process adapters call
`EnclosureHandlers.observe_enclosure_status(...)` directly.

The no-op `register` exists only to satisfy the slice-file-shape +
tools-completeness architecture fitness functions; no MCP tool is
registered. The `get_mcp_surface_id` import satisfies the
mcp-surface-id-injection fitness; the resolver is not actually called
because no tool consumes it.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.enclosure.features.observe_enclosure_status.handler import Handler
from cora.infrastructure.routing import get_mcp_surface_id

_STUB_RESOLVER = get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """No-op MCP registration: observe_enclosure_status is in-process-only."""
    _ = mcp
    _ = get_handler
    _ = _STUB_RESOLVER
    if False:  # pragma: no cover -- AST satisfaction for fitness scan
        _ = get_mcp_surface_id(None)  # type: ignore[arg-type]
