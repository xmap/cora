"""HTTP route for the `hold_visit` slice.

Action endpoint at `POST /visits/{visit_id}/hold`. Body carries `reason`.
204 on success.
"""

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
from cora.trust.features.hold_visit.command import HoldVisit
from cora.trust.features.hold_visit.handler import Handler


class HoldVisitRequest(BaseModel):
    """Body for `POST /visits/{visit_id}/hold`.

    `reason` is operator-supplied free text (audit-log breadcrumb).
    Examples: "beam dump", "equipment fault", "safety hold pending
    radiation door reset", "extended user break". MUST NOT contain PII.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied reason for the hold (audit-log breadcrumb; no PII).",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.hold_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits/{visit_id}/hold",
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
            "description": "Visit is not in InProgress status.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Hold an InProgress Visit (InProgress -> OnHold)",
)
async def post_visits_hold(
    visit_id: Annotated[UUID, Path(description="Target Visit's id.")],
    body: HoldVisitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        HoldVisit(visit_id=visit_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
