"""HTTP route for the `withdraw_edition` slice.

`POST /editions/{edition_id}/withdraw` returns 200 on success. The
mandatory `withdrawal_reason` rides in the request body.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from cora.data.features.withdraw_edition.command import WithdrawEdition
from cora.data.features.withdraw_edition.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class WithdrawEditionRequest(BaseModel):
    """Request body for `POST /editions/{edition_id}/withdraw`."""

    withdrawal_reason: Annotated[
        str,
        Field(
            min_length=1,
            max_length=REASON_MAX_LENGTH,
            description=(
                "Why the Edition is being withdrawn. Recorded forever on "
                "the DataCite tombstone; mandatory."
            ),
        ),
    ]


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.data.withdraw_edition
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/editions/{edition_id}/withdraw",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid withdrawal reason.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Edition not found.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Edition not in Published state.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "DoiMinter.tombstone failed.",
        },
    },
    summary="Withdraw a Published Edition",
)
async def post_editions_withdraw(
    edition_id: UUID,
    body: WithdrawEditionRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> Response:
    await handler(
        WithdrawEdition(
            edition_id=edition_id,
            withdrawal_reason=body.withdrawal_reason,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return Response(status_code=status.HTTP_200_OK)
