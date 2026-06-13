"""HTTP route for the `void_visit` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.features.void_visit.command import VoidVisit
from cora.trust.features.void_visit.handler import Handler


class VoidVisitRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/void`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason explaining why this Visit should "
            "never have existed (e.g., 'BSS double-sent registration', "
            "'duplicate of visit X'). No PII."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.void_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/void",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only reason).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Visit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Visit is in a terminal status (Completed/Cancelled/Aborted/Voided).",
        },
    },
    summary="Void a Visit (any non-terminal -> Voided). FHIR entered-in-error analog.",
)
async def post_visits_void(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: VoidVisitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VoidVisit(visit_id=visit_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
