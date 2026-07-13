"""HTTP route for the `void_allocation` slice.

Action endpoint at `POST /allocations/{allocation_id}/void`. Body
carries the REQUIRED withdrawal `reason`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class VoidAllocationRequest(BaseModel):
    """Body for `POST /allocations/{allocation_id}/void`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Why the grant is withdrawn. Required: voiding an award is a "
            "governance act the audit log must always carry context for."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.budget.void_allocation
    return handler


router = APIRouter(tags=["budget"])


@router.post(
    "/allocations/{allocation_id}/void",
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
            "description": "No Allocation exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Allocation is not in Granted or Active status (a sealed or "
                "voided envelope cannot be re-terminated)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing or "
                "over-length reason) or path parameter is not a UUID."
            ),
        },
    },
    summary="Void a Granted or Active Allocation (-> Voided)",
)
async def post_allocations_void(
    allocation_id: Annotated[UUID, Path(description="Target Allocation's id.")],
    body: VoidAllocationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VoidAllocation(allocation_id=allocation_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
