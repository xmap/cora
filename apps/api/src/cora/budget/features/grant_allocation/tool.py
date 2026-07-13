"""MCP tool for the `grant_allocation` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.budget.aggregates.allocation import ALLOCATION_NOTE_MAX_LENGTH
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class GrantAllocationOutput(BaseModel):
    """Structured output of the `grant_allocation` MCP tool."""

    allocation_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `grant_allocation` tool on the given MCP server."""

    @mcp.tool(
        name="grant_allocation",
        description=(
            "Grant a new spending envelope for this deployment's beamline "
            "(lands in Granted, dormant; a separate activation opens the "
            "spend window). Required: ceiling_usd, note. Optional: "
            "campaign_id (binds the award window to a Campaign), "
            "allocation_id (omit to mint server-side)."
        ),
    )
    async def grant_allocation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        ceiling_usd: Annotated[
            float,
            Field(
                gt=0.0,
                description="USD spending ceiling. Finite and greater than 0.",
            ),
        ],
        note: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ALLOCATION_NOTE_MAX_LENGTH,
                description="Operator-facing name for the envelope.",
            ),
        ],
        campaign_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional Campaign binding for the award window. Null "
                    "grants an unbound envelope."
                ),
            ),
        ] = None,
        allocation_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional caller-supplied id for configuration-seeded "
                    "envelopes. Null mints a server-side UUIDv7."
                ),
            ),
        ] = None,
    ) -> GrantAllocationOutput:
        handler = get_handler()
        new_id = await handler(
            GrantAllocation(
                ceiling_usd=ceiling_usd,
                note=note,
                campaign_id=campaign_id,
                allocation_id=allocation_id,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return GrantAllocationOutput(allocation_id=new_id)
