"""MCP tool for the `get_asset_integration_view` query slice.

Surfaces the same handler the REST route uses. Returns a structured
AssetIntegrationViewOutput on hit. On miss raises an exception that
FastMCP wraps as `isError: true` with a text diagnostic — matches the
REST 404 behaviour in MCP's error idiom (LLM consumers get a clear
"asset not found" message rather than null structuredContent they have
to interpret).

Read-time composition slice (v1 of the MTP-style bundle). See
[[project-asset-integration-view-design]] for the locked shape.
"""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.features.get_asset_integration_view.handler import Handler
from cora.equipment.features.get_asset_integration_view.query import GetAssetIntegrationView
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class FamilyOutput(BaseModel):
    """Structured output for one Family on the integration-view bundle."""

    family_id: UUID
    name: str
    affordances: list[str]


class PortOutput(BaseModel):
    """Structured output for one Asset port on the integration-view bundle."""

    name: str
    direction: str
    signal_type: str


class CautionOutput(BaseModel):
    """Structured output for one active Caution on the integration-view bundle."""

    caution_id: UUID
    category: str
    severity: str
    text: str


class CapabilityOutput(BaseModel):
    """Structured output for one applicable Capability on the integration-view bundle."""

    capability_id: UUID
    code: str
    name: str
    status: str


class AssetIntegrationViewOutput(BaseModel):
    """Structured output of the `get_asset_integration_view` MCP tool."""

    asset_id: UUID
    name: str
    tier: str
    lifecycle: str
    condition: str
    parent_id: UUID | None
    families: list[FamilyOutput]
    ports: list[PortOutput]
    settings: dict[str, Any]
    active_cautions: list[CautionOutput]
    applicable_capabilities: list[CapabilityOutput]
    incomplete: bool


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_asset_integration_view` tool on the given MCP server."""

    @mcp.tool(
        name="get_asset_integration_view",
        description=(
            "Get the consolidated integration-view bundle for an Asset: "
            "core fields (tier/lifecycle/condition/parent_id) + families "
            "(id+name+affordances) + ports + settings + active Cautions + "
            "applicable Capabilities (those whose required_affordances are "
            "covered by the Asset's combined Family affordances; Deprecated "
            "excluded). Use when integrating an Asset into a Plan: this one "
            "call replaces the multi-step walkthrough (get_asset + get_family "
            "per family + active-cautions query + applicable-capabilities query). "
            "Returns `incomplete: true` if any referenced Family failed to load."
        ),
    )
    async def get_asset_integration_view_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        asset_id: Annotated[
            UUID,
            Field(description="Target asset's id."),
        ],
    ) -> AssetIntegrationViewOutput:
        handler = get_handler()
        view = await handler(
            GetAssetIntegrationView(asset_id=asset_id),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if view is None:
            msg = f"Asset {asset_id} not found"
            raise ValueError(msg)
        return AssetIntegrationViewOutput(
            asset_id=view.asset_id,
            name=view.name,
            tier=view.tier,
            lifecycle=view.lifecycle,
            condition=view.condition,
            parent_id=view.parent_id,
            families=[
                FamilyOutput(
                    family_id=f.family_id,
                    name=f.name,
                    affordances=sorted(f.affordances),
                )
                for f in view.families
            ],
            ports=[
                PortOutput(
                    name=p.name,
                    direction=p.direction,
                    signal_type=p.signal_type,
                )
                for p in view.ports
            ],
            settings=view.settings,
            active_cautions=[
                CautionOutput(
                    caution_id=c.caution_id,
                    category=c.category,
                    severity=c.severity,
                    text=c.text,
                )
                for c in view.active_cautions
            ],
            applicable_capabilities=[
                CapabilityOutput(
                    capability_id=c.capability_id,
                    code=c.code,
                    name=c.name,
                    status=c.status,
                )
                for c in view.applicable_capabilities
            ],
            incomplete=view.incomplete,
        )
