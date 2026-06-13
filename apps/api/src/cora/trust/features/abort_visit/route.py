"""HTTP route for the `abort_visit` slice."""

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
from cora.trust.features.abort_visit.command import AbortVisit
from cora.trust.features.abort_visit.handler import Handler


class AbortVisitRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/abort`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied reason for the abort (no PII).",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.abort_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/abort",
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
            "description": (
                "Visit is not in InProgress or OnHold status (pre-work "
                "Visits must use cancel_visit; terminals refuse)."
            ),
        },
    },
    summary="Abort a mid-work Visit (InProgress | OnHold -> Aborted)",
)
async def post_visits_abort(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: AbortVisitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AbortVisit(visit_id=visit_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
