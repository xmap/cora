"""MCP tool for the `register_asset` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool.

`tier` accepts the StrEnum's string values; FastMCP's argument
schema enforces this. `parent_id` is `UUID | None`.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment._bodies import AlternateIdentifierBody, AssetOwnerBody, DrawingBody
from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH, AssetTier
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class RegisterAssetOutput(BaseModel):
    """Structured output of the `register_asset` MCP tool."""

    asset_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_asset` tool on the given MCP server."""

    @mcp.tool(
        name="register_asset",
        description=(
            "Register a new physical equipment asset with the given "
            "name, operational tier, and parent. A root Asset has null "
            "parent_id and binds facility_code; a non-root has a "
            "parent_id and no facility_code."
        ),
    )
    async def register_asset_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ASSET_NAME_MAX_LENGTH,
                description="Display name for the new asset.",
            ),
        ],
        tier: Annotated[
            AssetTier,
            Field(
                description="Operational tier: Unit, Component, or Device.",
            ),
        ],
        parent_id: Annotated[
            UUID | None,
            Field(
                description=(
                    "Immediate parent in the hierarchy tree. Must be "
                    "null for a root Asset (which binds facility_code); "
                    "required for all non-roots."
                ),
            ),
        ],
        drawing: Annotated[
            DrawingBody | None,
            Field(
                default=None,
                description=(
                    "Optional engineering reference for the physical "
                    "specimen (distinct from Mount.drawing, which "
                    "references the slot). Captured at registration only."
                ),
            ),
        ] = None,
        model_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional reference to the Model catalog entry "
                    "this Asset is an instance of. Set ONCE at "
                    "registration; rebind path is decommission + "
                    "re-register. Raises 404 if the Model stream "
                    "does not exist."
                ),
            ),
        ] = None,
        alternate_identifiers: Annotated[
            list[AlternateIdentifierBody] | None,
            Field(
                default=None,
                description=(
                    "Optional PIDINST v1.0 Property 13 alternate-"
                    "identifier tuples (operator-supplied serial "
                    "numbers, inventory tags, vendor-specific "
                    "schemes) seeded at registration. Each entry is "
                    "a flat (kind, value) pair; kind is closed "
                    "vocabulary SerialNumber | InventoryNumber | "
                    "Other."
                ),
            ),
        ] = None,
        owners: Annotated[
            list[AssetOwnerBody] | None,
            Field(
                default=None,
                description=(
                    "Optional PIDINST v1.0 Property 5 institutional "
                    "owner blocks seeded at registration. Each entry "
                    "carries a mandatory name plus optional contact, "
                    "identifier, and identifier_type (paired). Owner "
                    "names must be unique within the payload."
                ),
            ),
        ] = None,
        controller_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Optional reference to the controller Asset (a "
                    "sibling Device carrying the MotionController "
                    "Family) that drives this Asset. Set ONCE at "
                    "registration; rebind path is decommission + "
                    "re-register. Eventual-consistency: the "
                    "controller's existence is NOT verified."
                ),
            ),
        ] = None,
        facility_code: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=FACILITY_CODE_MAX_LENGTH,
                pattern=r"^[a-z0-9-]{1,32}$",
                description=(
                    "Optional cross-deployment Facility slug owning "
                    "this Asset (for example 'aps', 'maxiv'). Lowercase "
                    "ASCII alphanumeric plus dash, 1-32 chars. Set ONCE "
                    "at registration. Unknown codes raise 404; "
                    "Decommissioned-Facility binding is allowed."
                ),
            ),
        ] = None,
    ) -> RegisterAssetOutput:
        handler = get_handler()
        asset_id = await handler(
            RegisterAsset(
                name=name,
                tier=tier,
                parent_id=parent_id,
                drawing=drawing.to_domain() if drawing is not None else None,
                model_id=model_id,
                alternate_identifiers=frozenset(
                    entry.to_domain() for entry in (alternate_identifiers or [])
                ),
                owners=frozenset(entry.to_domain() for entry in (owners or [])),
                controller_id=controller_id,
                facility_code=facility_code,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterAssetOutput(asset_id=asset_id)
