"""MCP tool for the `register_facility` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. Mirrors the `register_credential` tool shape.

Alternate-identifier seeds are NOT exposed on the MCP tool today.
LLM-driven Facility onboarding is rare and the structured wire shape
would force a CLOSED nested model surface on every tool invocation
(per [[project_capability_settings_schema]] closed-vocabulary discipline).
Operators who need PIDINST seeds at registration go through the REST
route; the MCP path covers the common-case operator-onboards-facility
flow.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import FacilityKind
from cora.federation.features.register_facility.command import RegisterFacility
from cora.federation.features.register_facility.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class RegisterFacilityOutput(BaseModel):
    """Structured output of the `register_facility` MCP tool."""

    facility_id: UUID
    code: str


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_facility` tool on the given MCP server."""

    @mcp.tool(
        name="register_facility",
        description=(
            "Register a new federation Facility (genesis; lands in Active). "
            "Cross-deployment convergent code derives the deterministic "
            "stream id; codes are immutable post-creation. Required: code, "
            "display_name, kind. Required for kind=Area: parent_id."
        ),
    )
    async def register_facility_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        code: Annotated[
            str,
            Field(
                min_length=1,
                max_length=FACILITY_CODE_MAX_LENGTH,
                description=(
                    "Cross-deployment convergent facility slug (lowercase "
                    "ASCII alphanumeric and dash, 1-32 chars)."
                ),
            ),
        ],
        display_name: Annotated[
            str,
            Field(
                min_length=1,
                description="Operator-supplied display string (trimmed, 1-200 chars).",
            ),
        ],
        kind: Annotated[
            FacilityKind,
            Field(description="Closed enum: Site or Area."),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=("Parent Facility id. Omit for kind=Site. Required for kind=Area."),
            ),
        ] = None,
    ) -> RegisterFacilityOutput:
        handler = get_handler()
        facility_id = await handler(
            RegisterFacility(
                code=code,
                display_name=display_name,
                kind=kind,
                parent_id=FacilityId(parent_id) if parent_id is not None else None,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterFacilityOutput(facility_id=facility_id, code=code)
