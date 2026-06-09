"""MCP tool for the `decommission_enclosure` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors `decommission_facility`'s tool surface:
single UUID echo on output and a required free-text reason that flows
onto the `EnclosureDecommissioned` event payload.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.features.decommission_enclosure.command import DecommissionEnclosure
from cora.enclosure.features.decommission_enclosure.handler import Handler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class DecommissionEnclosureOutput(BaseModel):
    """Structured output of the `decommission_enclosure` MCP tool."""

    enclosure_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `decommission_enclosure` tool on the given MCP server."""

    @mcp.tool(
        name="decommission_enclosure",
        description=(
            "Decommission an Enclosure (terminal: Active -> Decommissioned). "
            "Strict-not-idempotent: decommissioning an already-Decommissioned "
            "enclosure raises. The last observed permit_status is preserved on "
            "the aggregate as audit trail; the terminal transition itself does "
            "not mutate permit_status."
        ),
    )
    async def decommission_enclosure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        enclosure_id: Annotated[
            UUID,
            Field(description="Target enclosure's id."),
        ],
        reason: Annotated[
            str,
            Field(
                description=(
                    "Free-text operator intent for the decommission. "
                    "Flows onto the EnclosureDecommissioned event payload."
                ),
            ),
        ],
    ) -> DecommissionEnclosureOutput:
        handler = get_handler()
        await handler(
            DecommissionEnclosure(
                enclosure_id=EnclosureId(enclosure_id),
                reason=reason,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return DecommissionEnclosureOutput(enclosure_id=enclosure_id)
