"""MCP tool for the `register_enclosure` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors the `register_supply` tool shape:
no two-tier identity (single UUID return) and no nested closed-vocabulary
bodies on the tool surface.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.enclosure.aggregates.enclosure import ENCLOSURE_NAME_MAX_LENGTH
from cora.enclosure.features.register_enclosure.command import RegisterEnclosure
from cora.enclosure.features.register_enclosure.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class RegisterEnclosureOutput(BaseModel):
    """Structured output of the `register_enclosure` MCP tool."""

    enclosure_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_enclosure` tool on the given MCP server."""

    @mcp.tool(
        name="register_enclosure",
        description=(
            "Register a new interlocked enclosure (hutch, cave, shielded volume) "
            "containing one or more beamline assets. Enclosure lands in 'Active' "
            "lifecycle with permit_status='Unknown'; permit observations arrive "
            "via subsequent monitor or operator slices."
        ),
    )
    async def register_enclosure_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ENCLOSURE_NAME_MAX_LENGTH,
                description="Operator-readable display name for this Enclosure instance.",
            ),
        ],
        facility_code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FACILITY_CODE_MAX_LENGTH,
                pattern=r"^[a-z0-9-]{1,32}$",
                description=(
                    "Cross-deployment Facility slug for the Site / Area this "
                    "enclosure sits within (for example 'aps', 'maxiv'). "
                    "Lowercase ASCII alphanumeric plus dash, 1-32 chars. "
                    "Unknown codes raise HTTP 404."
                ),
            ),
        ],
    ) -> RegisterEnclosureOutput:
        handler = get_handler()
        enclosure_id = await handler(
            RegisterEnclosure(name=name, facility_code=facility_code),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterEnclosureOutput(enclosure_id=enclosure_id)
