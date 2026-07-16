"""HTTP route for the `grant_allocation` slice.

`POST /allocations` with body carrying ceiling_usd / note +
optional campaign_id / allocation_id. Returns 201 + `{allocation_id}`
on success.

`ceiling_usd` gets only a loose `gt=0` bound at the boundary; the
finite-and-positive rule is a domain concern the decider enforces,
so NaN / infinity map to 400 InvalidAllocationCeilingError rather
than 422.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.budget.aggregates.allocation import ALLOCATION_NOTE_MAX_LENGTH
from cora.budget.features.grant_allocation.command import GrantAllocation
from cora.budget.features.grant_allocation.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class GrantAllocationRequest(BaseModel):
    """Body for `POST /allocations`."""

    ceiling_usd: float = Field(
        ...,
        gt=0.0,
        description="USD spending ceiling for the envelope. Finite and greater than 0.",
    )
    note: str = Field(
        ...,
        min_length=1,
        max_length=ALLOCATION_NOTE_MAX_LENGTH,
        description=(
            "Operator-facing name for the envelope (award cycle, proposal "
            "block). The holder itself is implicitly this deployment's beamline."
        ),
    )
    campaign_id: UUID | None = Field(
        default=None,
        description=(
            "Optional Campaign binding for the award window. When set, the "
            "CampaignClosed subscriber seals this envelope beside the "
            "campaign's own books. Pass null for an unbound envelope."
        ),
    )
    allocation_id: UUID | None = Field(
        default=None,
        description=(
            "Optional caller-supplied id for configuration-seeded envelopes "
            "needing stable ids across environments. Omit (or pass null) to "
            "let the server mint a UUIDv7."
        ),
    )


class GrantAllocationResponse(BaseModel):
    """Response body for `POST /allocations`."""

    allocation_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.budget.grant_allocation
    return handler


router = APIRouter(tags=["budget"])


@router.post(
    "/allocations",
    status_code=status.HTTP_201_CREATED,
    response_model=GrantAllocationResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (non-finite ceiling, whitespace-only note)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The target Allocation stream already has events. Reachable "
                "in practice only with a caller-supplied allocation_id; "
                "essentially impossible for server-minted UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, length "
                "out of bounds, non-positive ceiling, invalid UUID), OR "
                "Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Grant a new spending envelope (lands in Granted, dormant)",
)
async def post_allocations(
    body: GrantAllocationRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> GrantAllocationResponse:
    allocation_id = await handler(
        GrantAllocation(
            ceiling_usd=body.ceiling_usd,
            note=body.note,
            campaign_id=body.campaign_id,
            allocation_id=body.allocation_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return GrantAllocationResponse(allocation_id=allocation_id)
