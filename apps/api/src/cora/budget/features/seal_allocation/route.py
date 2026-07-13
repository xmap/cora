"""HTTP route for the `seal_allocation` slice.

Action endpoint at `POST /allocations/{allocation_id}/seal`. Body
carries only the optional closing `reason`; the final-spend snapshot
is computed server-side by the handler's TotalSpendReader (a caller
can never assert a figure the ledger does not support, so spent_usd
is deliberately NOT on the wire). 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.budget.features.seal_allocation.command import SealAllocation
from cora.budget.features.seal_allocation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class SealAllocationRequest(BaseModel):
    """Body for `POST /allocations/{allocation_id}/seal`."""

    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Optional closing note (an early close usually carries context; "
            "a routine end-of-window seal needs none). Pass null to omit."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.budget.seal_allocation
    return handler


router = APIRouter(tags=["budget"])


@router.post(
    "/allocations/{allocation_id}/seal",
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
                "Allocation is not in Active status (seal_allocation closes "
                "an open spend window; void a dormant grant instead)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (reason length out of "
                "bounds) or path parameter is not a UUID."
            ),
        },
    },
    summary="Seal an Active Allocation (Active -> Sealed, closing the books)",
)
async def post_allocations_seal(
    allocation_id: Annotated[UUID, Path(description="Target Allocation's id.")],
    body: SealAllocationRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        SealAllocation(allocation_id=allocation_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
