"""HTTP route for the `suspend_permit` slice.

Action endpoint at `POST /federation/permits/{permit_id}/suspend`.
Optional `reason` body field flows through to the emitted
`PermitSuspended` event payload so operator context survives on the
immutable event log. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.federation.features.suspend_permit.command import SuspendPermit
from cora.federation.features.suspend_permit.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SuspendPermitRequest(BaseModel):
    """Body for `POST /federation/permits/{permit_id}/suspend`.

    `reason` is operator-supplied free text (audit-log breadcrumb)
    explaining why the Permit is being suspended. Examples: "peer
    facility paused outbound sharing pending PII review",
    "credential rotation in progress, expected back in 24h".
    """

    reason: str | None = Field(
        default=None,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional operator-supplied reason for suspending the permit (audit-log breadcrumb)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.federation.suspend_permit
    return handler


router = APIRouter(tags=["federation"])


@router.post(
    "/federation/permits/{permit_id}/suspend",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No permit exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Permit is not in `Active` status (suspend_permit requires "
                "Active; Defined/Suspended/Revoked permits are rejected)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": ("Request body failed schema validation (reason exceeds 500 chars)."),
        },
    },
    summary="Suspend an Active Permit (Active -> Suspended)",
)
async def post_permits_suspend(
    permit_id: Annotated[UUID, Path(description="Target permit's id.")],
    body: SuspendPermitRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SuspendPermit(permit_id=permit_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
