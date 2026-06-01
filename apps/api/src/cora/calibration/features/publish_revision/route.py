"""HTTP route for the `publish_revision` slice.

Action endpoint at
`POST /calibrations/{calibration_id}/revisions/{revision_id}/publish`.
201 + body `{receipt_id}` on success. Idempotency-Key wrapped per
the design memo so retries do not double-publish.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.calibration.features.publish_revision.command import (
    PublishCalibrationRevision,
)
from cora.calibration.features.publish_revision.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class PublishCalibrationRevisionRequest(BaseModel):
    """Body for `POST /calibrations/{id}/revisions/{revision_id}/publish`."""

    peer_facility_id: str = Field(
        ...,
        description=(
            "Opaque id of the peer facility this publication is targeted at. "
            "Resolved at the handler via PermitLookup to locate the matching "
            "Active outbound Permit; missing or inactive permits raise 409."
        ),
    )


class PublishCalibrationRevisionResponse(BaseModel):
    """Response body for the publish action."""

    receipt_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.calibration.publish_revision
    return handler


router = APIRouter(tags=["calibration"])


@router.post(
    "/calibrations/{calibration_id}/revisions/{revision_id}/publish",
    status_code=status.HTTP_201_CREATED,
    response_model=PublishCalibrationRevisionResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the publish command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No calibration or no revision exists with the given ids.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Publish-time FSM rejection: revision lacks content_hash, "
                "or no Active outbound Permit authorizes publishing this "
                "artifact to the peer."
            ),
        },
    },
    summary="Publish an existing Calibration revision to a peer facility",
)
async def post_publish_calibration_revision(
    calibration_id: Annotated[UUID, Path(description="Target calibration's id.")],
    revision_id: Annotated[UUID, Path(description="Revision on that calibration to publish.")],
    body: PublishCalibrationRevisionRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PublishCalibrationRevisionResponse:
    receipt_id = await handler(
        PublishCalibrationRevision(
            calibration_id=calibration_id,
            revision_id=revision_id,
            peer_facility_id=body.peer_facility_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return PublishCalibrationRevisionResponse(receipt_id=receipt_id)
