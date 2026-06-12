"""HTTP route for the `seal_edition` slice.

`POST /editions/{edition_id}/seal` returns 200 + empty body on
success. Body fields are optional overrides; any combination may be
sent.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from cora.data.aggregates.edition import (
    EDITION_LICENSE_MAX_LENGTH,
)
from cora.data.features.seal_edition.command import SealEdition
from cora.data.features.seal_edition.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class SealEditionRequest(BaseModel):
    """Optional overrides for `POST /editions/{edition_id}/seal`."""

    publisher_facility_code: str | None = Field(
        default=None,
        description=(
            "Override the Edition's publisher Facility code (resolved via "
            "FacilityLookup). When omitted, the value set at register-time "
            "is used; when neither is set the seal is rejected with 404."
        ),
    )
    publication_year_override: int | None = Field(
        default=None,
        description=(
            "Override the Edition's publication year. When omitted, the "
            "value set at register-time is used; when neither is set the "
            "sealing-clock UTC year is used."
        ),
    )
    license_override: str | None = Field(
        default=None,
        max_length=EDITION_LICENSE_MAX_LENGTH,
        description=(
            "Override the Edition's SPDX license identifier. Required for "
            "kind in {DataCite, Croissant} when no license was supplied at "
            "register-time."
        ),
    )

    model_config = {"extra": "forbid"}


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.seal_edition
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/editions/{edition_id}/seal",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g., malformed license).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Edition not found, publisher Facility not found, member "
                "Dataset has no canonical Distribution, or a member Dataset "
                "is missing."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Domain conflict: status not Registered, license required "
                "for kind, member Dataset Discarded, or member Dataset not "
                "Production intent."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "EditionSerializer failed.",
        },
    },
    summary="Seal a Registered Edition",
)
async def post_editions_seal(
    edition_id: UUID,
    body: SealEditionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> Response:
    await handler(
        SealEdition(
            edition_id=edition_id,
            publisher_facility_code=body.publisher_facility_code,
            publication_year_override=body.publication_year_override,
            license_override=body.license_override,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return Response(status_code=status.HTTP_200_OK)
