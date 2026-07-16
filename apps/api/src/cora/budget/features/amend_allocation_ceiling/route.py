"""HTTP route for the `amend_allocation_ceiling` slice.

Action endpoint at `POST /allocations/{allocation_id}/ceiling`. Body
carries `ceiling_usd`. PUT semantics: the supplied ceiling IS the
post-amend ceiling. 204 No Content on success (including the
idempotent no-op case), the update_agent_budget shape.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.budget.features.amend_allocation_ceiling.command import AmendAllocationCeiling
from cora.budget.features.amend_allocation_ceiling.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AmendAllocationCeilingRequest(BaseModel):
    """Body for `POST /allocations/{allocation_id}/ceiling`."""

    ceiling_usd: float = Field(
        ...,
        gt=0.0,
        description=(
            "The post-amend USD ceiling (PUT semantics, not a delta). Finite and greater than 0."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.budget.amend_allocation_ceiling
    return handler


router = APIRouter(tags=["budget"])


@router.post(
    "/allocations/{allocation_id}/ceiling",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (non-finite ceiling).",
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
                "Allocation is not in Granted or Active status "
                "(amend_allocation_ceiling cannot rewrite a closed envelope)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "non-positive ceiling) or path parameter is not a UUID."
            ),
        },
    },
    summary="Amend an Allocation's USD ceiling (PUT semantics)",
)
async def post_allocations_ceiling(
    allocation_id: Annotated[UUID, Path(description="Target Allocation's id.")],
    body: AmendAllocationCeilingRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AmendAllocationCeiling(allocation_id=allocation_id, ceiling_usd=body.ceiling_usd),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
