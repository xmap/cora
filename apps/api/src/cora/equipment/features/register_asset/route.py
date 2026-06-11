"""HTTP route for the `register_asset` slice.

Pydantic request/response schemas + APIRouter for `POST /assets`.
The slice's BC-level wiring (`cora.equipment.routes.register_equipment_routes`)
includes this router on the FastAPI app.

Pydantic enforces `tier` is a valid `AssetTier` value at the API
boundary (Pydantic→422 on unknown tier strings); the decider
trusts its inputs and only enforces domain invariants (anchoring
XOR rule, name VO).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment._alternate_identifier_body import AlternateIdentifierBody
from cora.equipment._asset_owner_body import AssetOwnerBody
from cora.equipment._drawing_body import DrawingBody
from cora.equipment.aggregates.asset import ASSET_NAME_MAX_LENGTH, AssetTier
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.equipment.features.register_asset.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class RegisterAssetRequest(BaseModel):
    """Body for `POST /assets`.

    `tier` accepts the StrEnum's PascalCase string values
    ("Unit" / "Component" / "Device"); Pydantic rejects unknowns
    with 422.

    `parent_id` and `facility_code` follow the anchoring XOR rule:
    a root Asset has null `parent_id` + a `facility_code`; a
    non-root has a `parent_id` + null `facility_code`. That's a
    domain invariant enforced by the decider (raises
    InvalidAssetParentError → 400), not by Pydantic.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=ASSET_NAME_MAX_LENGTH,
        description="Display name for the new asset.",
    )
    tier: AssetTier = Field(
        ...,
        description="Operational tier. One of: Unit, Component, Device.",
    )
    parent_id: UUID | None = Field(
        ...,
        description=(
            "Immediate parent in the hierarchy tree. Must be null for a "
            "root Asset (which binds facility_code instead); required for "
            "all non-roots. Eventual-consistency: parent's existence is "
            "NOT verified."
        ),
    )
    drawing: DrawingBody | None = Field(
        None,
        description=(
            "Optional engineering reference for the physical specimen "
            "(distinct from Mount.drawing, which references the slot). "
            "Captured at registration only; not mutable in v1."
        ),
    )
    model_id: UUID | None = Field(
        None,
        description=(
            "Optional reference to the Model catalog entry this Asset "
            "is an instance of (Family -> Model -> Assembly -> Asset "
            "ladder). Set ONCE at registration; rebind path is "
            "decommission + re-register. The handler verifies the "
            "Model stream exists before invoking the decider (404 if "
            "missing); no subset check at register time because the "
            "genesis Asset families set is empty."
        ),
    )
    alternate_identifiers: list[AlternateIdentifierBody] | None = Field(
        None,
        description=(
            "Optional PIDINST v1.0 Property 13 alternate-identifier "
            "tuples (operator-supplied serial numbers, inventory tags, "
            "vendor-specific schemes) seeded at registration. Each "
            "entry is a flat (kind, value) pair; kind is closed "
            "vocabulary SerialNumber | InventoryNumber | Other. "
            "Cross-Asset uniqueness on (kind, value) is NOT enforced "
            "in v1."
        ),
    )
    owners: list[AssetOwnerBody] | None = Field(
        None,
        description=(
            "Optional PIDINST v1.0 Property 5 institutional owner "
            "blocks seeded at registration. Each entry carries a "
            "mandatory `name` plus optional `contact`, `identifier`, "
            "and `identifier_type`. Owner names must be unique within "
            "the payload (rejected as 409 otherwise). Aggregate "
            "allows 0-n owners; the PIDINST serializer enforces the "
            "1-n cardinality at emission time."
        ),
    )
    controller_id: UUID | None = Field(
        None,
        description=(
            "Optional reference to the controller Asset (a sibling "
            "Device carrying the MotionController Family) that drives "
            "this Asset. Set ONCE at registration; rebind path is "
            "decommission + re-register (matches the operational "
            "semantics of a physical controller swap). Eventual-"
            "consistency: the controller's existence is NOT verified."
        ),
    )
    facility_code: str | None = Field(
        None,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Optional cross-deployment Facility slug owning this Asset "
            "(for example 'aps', 'maxiv'). Lowercase ASCII alphanumeric "
            "plus dash, 1-32 chars. Set ONCE at registration; rebind "
            "path is decommission + re-register. The handler resolves "
            "the slug via the Federation BC's FacilityLookup port; "
            "unknown codes raise HTTP 404. Decommissioned-Facility "
            "binding is allowed."
        ),
    )


class RegisterAssetResponse(BaseModel):
    """Response body for `POST /assets`."""

    asset_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.register_asset
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterAssetResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name, "
                "anchoring XOR rule (a root must have null parent_id + a "
                "facility_code; a non-root must have a parent_id + no "
                "facility_code), invalid Drawing (empty number, overlong "
                "revision, etc.), or invalid AlternateIdentifier value "
                "(empty after trimming, exceeds 200 chars)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Either model_id was supplied but the referenced Model "
                "stream does not exist (ModelNotFoundError), OR "
                "facility_code was supplied but the referenced Facility "
                "is not visible in the Federation projection "
                "(AssetFacilityNotFoundError). Operator remedies: "
                "register the missing parent first "
                "(`POST /federation/facilities` or via the model "
                "registration slice), or correct the slug / id."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Two or more entries in the owners payload share a "
                "name (AssetOwnerAlreadyPresentError); owner names "
                "must be unique within a single Asset."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (unknown tier, "
                "missing fields, malformed UUID) OR Idempotency-Key was "
                "reused with a different request body."
            ),
        },
    },
    summary="Register a new physical equipment asset",
)
async def post_assets(
    body: RegisterAssetRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the asset."
            ),
        ),
    ] = None,
) -> RegisterAssetResponse:
    asset_id = await handler(
        RegisterAsset(
            name=body.name,
            tier=body.tier,
            parent_id=body.parent_id,
            drawing=body.drawing.to_domain() if body.drawing is not None else None,
            model_id=body.model_id,
            alternate_identifiers=frozenset(
                entry.to_domain() for entry in (body.alternate_identifiers or [])
            ),
            owners=frozenset(entry.to_domain() for entry in (body.owners or [])),
            controller_id=body.controller_id,
            facility_code=body.facility_code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterAssetResponse(asset_id=asset_id)
