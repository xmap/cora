"""HTTP route for the `get_asset_integration_view` query slice.

`GET /assets/{asset_id}/integration-view` returns 200 + AssetIntegrationViewResponse
on hit, 404 on miss. The handler returns `AssetIntegrationView | None`;
the route maps None to 404 via HTTPException (idiomatic in routes;
the BC's exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).

Read-time composition slice (v1 of the MTP-style bundle). See
[[project-asset-integration-view-design]] for the locked shape.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.equipment.features.get_asset_integration_view.handler import Handler
from cora.equipment.features.get_asset_integration_view.query import GetAssetIntegrationView
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class FamilyViewDTO(BaseModel):
    """Read-side DTO for one Family on the integration-view bundle."""

    family_id: UUID
    name: str
    affordances: list[str]


class PortViewDTO(BaseModel):
    """Read-side DTO for one Asset port on the integration-view bundle."""

    name: str
    direction: str
    signal_type: str


class CautionViewDTO(BaseModel):
    """Read-side DTO for one active Caution on the integration-view bundle."""

    caution_id: UUID
    category: str
    severity: str
    text: str


class CapabilityViewDTO(BaseModel):
    """Read-side DTO for one applicable Capability on the integration-view bundle."""

    capability_id: UUID
    code: str
    name: str
    status: str


class AssetIntegrationViewResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Decouples wire format from the domain `AssetIntegrationView`. Lists
    serialize in deterministic order (families/cautions/capabilities by
    their canonical sort; ports already sorted by name in the handler).

    `incomplete` is TRUE if any Family in `asset.family_ids` failed to load
    (eventual-consistency tolerance per
    [[project-dataset-lineage-design]]); consumers should treat the
    bundle as partial in that case.
    """

    asset_id: UUID
    name: str
    tier: str
    lifecycle: str
    condition: str
    parent_id: UUID | None
    families: list[FamilyViewDTO]
    ports: list[PortViewDTO]
    settings: dict[str, Any]
    active_cautions: list[CautionViewDTO]
    applicable_capabilities: list[CapabilityViewDTO]
    incomplete: bool


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_asset_integration_view
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/assets/{asset_id}/integration-view",
    status_code=status.HTTP_200_OK,
    response_model=AssetIntegrationViewResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No asset exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get the integration-view bundle for an asset",
)
async def get_assets_integration_view(
    asset_id: Annotated[UUID, Path(description="Target asset's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AssetIntegrationViewResponse:
    view = await handler(
        GetAssetIntegrationView(asset_id=asset_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )
    return AssetIntegrationViewResponse(
        asset_id=view.asset_id,
        name=view.name,
        tier=view.tier,
        lifecycle=view.lifecycle,
        condition=view.condition,
        parent_id=view.parent_id,
        families=[
            FamilyViewDTO(
                family_id=f.family_id,
                name=f.name,
                affordances=sorted(f.affordances),
            )
            for f in view.families
        ],
        ports=[
            PortViewDTO(
                name=p.name,
                direction=p.direction,
                signal_type=p.signal_type,
            )
            for p in view.ports
        ],
        settings=view.settings,
        active_cautions=[
            CautionViewDTO(
                caution_id=c.caution_id,
                category=c.category,
                severity=c.severity,
                text=c.text,
            )
            for c in view.active_cautions
        ],
        applicable_capabilities=[
            CapabilityViewDTO(
                capability_id=c.capability_id,
                code=c.code,
                name=c.name,
                status=c.status,
            )
            for c in view.applicable_capabilities
        ],
        incomplete=view.incomplete,
    )
