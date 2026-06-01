"""HTTP route for the `define_model` slice.

Pydantic request/response schemas + APIRouter for `POST /models`.
The slice's BC-level wiring (`cora.equipment.routes.register_equipment_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
    MODEL_VERSION_TAG_MAX_LENGTH,
    Manufacturer,
    ManufacturerIdentifier,
    ManufacturerIdentifierType,
    ManufacturerName,
)
from cora.equipment.features.define_model.command import DefineModel
from cora.equipment.features.define_model.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ManufacturerBody(BaseModel):
    """Pydantic mirror of the Manufacturer VO for the request body.

    `identifier` and `identifier_type` are both optional but must be
    supplied together or both omitted (the pairing invariant is
    enforced at the VO constructor; a bare identifier with no scheme
    cannot be resolved).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=MANUFACTURER_NAME_MAX_LENGTH,
        description="Display name of the manufacturer.",
    )
    identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH,
        description=(
            "Optional opaque identifier value. If supplied, `identifier_type` "
            "is required (and vice versa)."
        ),
    )
    identifier_type: ManufacturerIdentifierType | None = Field(
        default=None,
        description="Closed scheme for the optional manufacturer identifier.",
    )

    def to_vo(self) -> Manufacturer:
        identifier = (
            ManufacturerIdentifier(self.identifier) if self.identifier is not None else None
        )
        return Manufacturer(
            name=ManufacturerName(self.name),
            identifier=identifier,
            identifier_type=self.identifier_type,
        )


class DefineModelRequest(BaseModel):
    """Body for `POST /models`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_NAME_MAX_LENGTH,
        description="Display name for the new Model.",
    )
    manufacturer: ManufacturerBody = Field(
        ...,
        description="Vendor identity (name plus optional ROR/GRID/ISNI identifier).",
    )
    part_number: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_PART_NUMBER_MAX_LENGTH,
        description=(
            "Vendor SKU; case-sensitive (RV120CCHL and rv120cchl are different Newport entries)."
        ),
    )
    declared_families: list[UUID] = Field(
        ...,
        min_length=1,
        description=(
            "Family ids the catalog entry satisfies. At least one required; "
            "deduplicated server-side."
        ),
    )
    version_tag: str | None = Field(
        default=None,
        min_length=1,
        max_length=MODEL_VERSION_TAG_MAX_LENGTH,
        description="Optional initial revision label (e.g., 'rev-A').",
    )


class DefineModelResponse(BaseModel):
    """Response body for `POST /models`."""

    model_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.define_model
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/models",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineModelResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "One or more declared families does not resolve to a registered Family.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new vendor-catalog Model",
)
async def post_models(
    body: DefineModelRequest,
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
                "response instead of re-creating the model."
            ),
        ),
    ] = None,
) -> DefineModelResponse:
    model_id = await handler(
        DefineModel(
            name=body.name,
            manufacturer=body.manufacturer.to_vo(),
            part_number=body.part_number,
            declared_families=frozenset(body.declared_families),
            version_tag=body.version_tag,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineModelResponse(model_id=model_id)
