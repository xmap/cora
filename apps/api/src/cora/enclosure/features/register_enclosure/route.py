"""HTTP route for the `register_enclosure` slice.

Pydantic request/response schemas + APIRouter for `POST /enclosures`.
The slice's BC-level wiring (`cora.enclosure.routes.register_enclosure_routes`)
includes this router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.enclosure.aggregates.enclosure import ENCLOSURE_NAME_MAX_LENGTH
from cora.enclosure.features.register_enclosure.command import RegisterEnclosure
from cora.enclosure.features.register_enclosure.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.facility_code import FACILITY_CODE_MAX_LENGTH


class RegisterEnclosureRequest(BaseModel):
    """Body for `POST /enclosures`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ENCLOSURE_NAME_MAX_LENGTH,
        description=(
            "Operator-readable display name for this Enclosure instance "
            "(for example '2-BM-A hutch', 'sample-prep cabinet'). "
            "Uniqueness within a containing Facility (while Active) is "
            "enforced by the projection-tier UNIQUE INDEX."
        ),
    )
    facility_code: str = Field(
        ...,
        min_length=1,
        max_length=FACILITY_CODE_MAX_LENGTH,
        pattern=r"^[a-z0-9-]{1,32}$",
        description=(
            "Cross-deployment Facility slug for the Site / Area this "
            "Enclosure sits within (for example 'aps', 'maxiv'). "
            "Lowercase ASCII alphanumeric plus dash, 1-32 chars. The "
            "handler resolves the slug via the Federation BC's "
            "FacilityLookup port; unknown codes raise HTTP 404. The "
            "address tuple (facility_code, name) is unique while "
            "lifecycle=Active."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterEnclosureResponse(BaseModel):
    """Response body for `POST /enclosures`."""

    enclosure_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.enclosure.register_enclosure
    return handler


router = APIRouter(tags=["enclosure"])


@router.post(
    "/enclosures",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterEnclosureResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (for example whitespace-only name "
                "rejected by the EnclosureName value object past the Pydantic "
                "length bounds)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "The supplied facility_code does not resolve to a known Federation Facility."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The address tuple (facility_code, name) collides with an "
                "Active Enclosure already registered within the same "
                "containing Facility."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "invalid UUID, length out of bounds), OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new interlock-gated Enclosure (lands in Unknown)",
)
async def post_enclosures(
    body: RegisterEnclosureRequest,
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
                "response instead of re-creating the enclosure."
            ),
        ),
    ] = None,
) -> RegisterEnclosureResponse:
    enclosure_id = await handler(
        RegisterEnclosure(
            name=body.name,
            facility_code=body.facility_code,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterEnclosureResponse(enclosure_id=enclosure_id)
