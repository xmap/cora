"""HTTP route for the `get_model` query slice.

`GET /models/{model_id}` returns 200 + ModelResponse on hit, 404 on
miss. The handler returns `Model | None`; the route maps None to 404
via HTTPException (idiomatic in routes; the BC's exception-handler
infrastructure stays focused on domain / application errors raised
deeper in the stack).

Response carries the vendor-catalog state: the `manufacturer` is a
nested `ManufacturerResponse` (required name plus optional opaque
identifier and closed-enum scheme), `declared_families` is the
sorted list of Family ids the catalog entry satisfies, `status` is
the StrEnum string value (Defined / Versioned / Deprecated), and
`version_tag` is the operator-supplied label of the most recent
`version_model` call (null until first version).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.model import (
    MANUFACTURER_IDENTIFIER_MAX_LENGTH,
    MANUFACTURER_NAME_MAX_LENGTH,
    MODEL_NAME_MAX_LENGTH,
    MODEL_PART_NUMBER_MAX_LENGTH,
)
from cora.equipment.features.get_model.handler import Handler
from cora.equipment.features.get_model.query import GetModel
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ManufacturerResponse(BaseModel):
    """Nested DTO for a model's manufacturer.

    `name` is required; `identifier` and `identifier_type` are both
    set or both null (pairing invariant enforced by the domain VO).
    `identifier_type` is the closed-StrEnum scheme string value
    (ROR / GRID / ISNI) when present.
    """

    name: str = Field(..., max_length=MANUFACTURER_NAME_MAX_LENGTH)
    identifier: str | None = Field(default=None, max_length=MANUFACTURER_IDENTIFIER_MAX_LENGTH)
    identifier_type: str | None = None


class ModelResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `status` is the StrEnum's string value (Defined / Versioned /
    Deprecated). `version_tag` is the operator-supplied label of the
    most recent version_model call (null until first version).
    `declared_families` serializes as a sorted list of Family UUIDs
    (frozenset semantics in domain state, list at the JSON boundary;
    sorted by UUID string form for response determinism).
    """

    model_id: UUID
    name: str = Field(..., max_length=MODEL_NAME_MAX_LENGTH)
    manufacturer: ManufacturerResponse
    part_number: str = Field(..., max_length=MODEL_PART_NUMBER_MAX_LENGTH)
    declared_families: list[UUID]
    status: str
    version_tag: str | None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.get_model
    return handler


router = APIRouter(tags=["equipment"])


@router.get(
    "/models/{model_id}",
    status_code=status.HTTP_200_OK,
    response_model=ModelResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No model exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a model by id",
)
async def get_models(
    model_id: Annotated[UUID, Path(description="Target model's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ModelResponse:
    model = await handler(
        GetModel(model_id=model_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )
    manufacturer = model.manufacturer
    return ModelResponse(
        model_id=model.id,
        name=model.name.value,
        manufacturer=ManufacturerResponse(
            name=manufacturer.name.value,
            identifier=(
                manufacturer.identifier.value if manufacturer.identifier is not None else None
            ),
            identifier_type=(
                manufacturer.identifier_type.value
                if manufacturer.identifier_type is not None
                else None
            ),
        ),
        part_number=model.part_number.value,
        declared_families=sorted(model.declared_families, key=str),
        status=model.status.value,
        version_tag=model.version,
    )
