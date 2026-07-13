"""HTTP route for the `activate_allocation` slice.

Action endpoint at `POST /allocations/{allocation_id}/activate`.
Empty body. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status

from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.budget.activate_allocation
    return handler


router = APIRouter(tags=["budget"])


@router.post(
    "/allocations/{allocation_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
                "Allocation is not in Granted status (activate_allocation is "
                "single-source from Granted only)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Activate a Granted Allocation (Granted -> Active)",
)
async def post_allocations_activate(
    allocation_id: Annotated[UUID, Path(description="Target Allocation's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        ActivateAllocation(allocation_id=allocation_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
