"""HTTP route for the `deny_ratification` slice.

Action endpoint at `POST /ratifications/{ratification_id}/deny`. Body carries
`reason`. 204 on success.
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
from cora.trust.features.deny_ratification.command import DenyRatification
from cora.trust.features.deny_ratification.handler import Handler


class DenyRatificationRequest(BaseModel):
    """Body for `POST /ratifications/{ratification_id}/deny`.

    `reason` is operator-supplied free text (audit-log breadcrumb) explaining
    the refusal. MUST NOT contain PII.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description="Operator-supplied reason for the denial (audit-log breadcrumb; no PII).",
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.deny_ratification
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/ratifications/{ratification_id}/deny",
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
            "description": "No Ratification exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Ratification is not in Requested status, or denier is the requester.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Deny (refuse) a Requested Ratification (Requested -> Denied)",
)
async def post_ratifications_deny(
    ratification_id: Annotated[UUID, Path(description="Target Ratification's id.")],
    body: DenyRatificationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DenyRatification(ratification_id=ratification_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
