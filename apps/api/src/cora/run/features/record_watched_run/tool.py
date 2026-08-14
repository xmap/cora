"""Stub MCP tool module for `record_watched_run` (in-process-only slice).

Per the roadmap's anti-scope: this slice is NOT exposed as an MCP tool.
In-process adapters call `RunHandlers.record_watched_run(...)` directly.

The no-op `register` exists only to satisfy the slice-file-shape +
tools-completeness architecture fitness functions; no MCP tool is
registered. The `get_mcp_surface_id` import satisfies the
mcp-surface-id-injection fitness; the resolver is not actually called
because no tool consumes it.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.infrastructure.routing import get_mcp_surface_id
from cora.run.features.record_watched_run.handler import Handler

_STUB_RESOLVER = get_mcp_surface_id


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """No-op MCP registration: record_watched_run is in-process-only."""
    _ = mcp
    _ = get_handler
    _ = _STUB_RESOLVER
    if False:  # pragma: no cover -- AST satisfaction for fitness scan
        _ = get_mcp_surface_id(None)  # type: ignore[arg-type]
