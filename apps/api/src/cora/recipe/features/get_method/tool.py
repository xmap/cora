"""MCP tool for the `get_method` query slice.

Surfaces the same handler the REST route uses. Returns a structured
MethodOutput on hit. On miss raises an exception that FastMCP wraps
as `isError: true` with a text diagnostic — matches the REST 404
behaviour in MCP's error idiom (LLM consumers get a clear "method
not found" message rather than null structuredContent they have to
interpret).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.recipe.aggregates.method import METHOD_NAME_MAX_LENGTH
from cora.recipe.features.get_method.handler import Handler
from cora.recipe.features.get_method.query import GetMethod


class MethodOutput(BaseModel):
    """Structured output of the `get_method` MCP tool.

    `created_at` / `versioned_at` / `deprecated_at` mirror the REST
    `MethodResponse` (Path C): sourced from the
    `proj_recipe_method_summary` projection. Null semantics: read
    together with `status`: a populated `status` with a null
    timestamp means the projection has not yet folded that lifecycle
    event (transient eventual-consistency window), never a missing
    transition. A not-found Method raises (MCP `isError: true`)
    rather than returning null timestamps.
    """

    id: UUID
    name: str = Field(..., max_length=METHOD_NAME_MAX_LENGTH)
    needed_family_ids: list[UUID]
    needed_supplies: list[str]
    status: str
    version: str | None
    # compute classification, read from folded state (mirrors the REST
    # MethodResponse). execution_pattern is the enum string value
    # (Batch / Iterative / Streaming) or null; the two claims default False.
    execution_pattern: str | None
    monotone_quality: bool
    resumable_from_checkpoint: bool
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_method` tool on the given MCP server."""

    @mcp.tool(
        name="get_method",
        description="Read the current state of an existing method by id.",
    )
    async def get_method_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        method_id: Annotated[
            UUID,
            Field(description="Target method's id."),
        ],
    ) -> MethodOutput:
        handler = get_handler()
        view = await handler(
            GetMethod(method_id=method_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Method {method_id} not found"
            raise ValueError(msg)
        method = view.method
        timestamps = view.timestamps
        return MethodOutput(
            id=method.id,
            name=method.name.value,
            needed_family_ids=sorted(method.needed_family_ids, key=str),
            needed_supplies=sorted(method.needed_supplies),
            status=method.status.value,
            version=method.version,
            execution_pattern=(
                method.execution_pattern.value if method.execution_pattern is not None else None
            ),
            monotone_quality=method.monotone_quality,
            resumable_from_checkpoint=method.resumable_from_checkpoint,
            created_at=timestamps.created_at if timestamps is not None else None,
            versioned_at=timestamps.versioned_at if timestamps is not None else None,
            deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
        )
