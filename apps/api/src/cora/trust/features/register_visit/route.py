"""HTTP route for the `register_visit` slice.

Endpoint at `POST /visits`. Caller supplies the `visit_id` (genesis
collision raises 409 via central `_handle_already_exists`).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import VisitType
from cora.trust.features.register_visit.command import RegisterVisit
from cora.trust.features.register_visit.handler import IdempotentHandler


class _IdentifierBody(BaseModel):
    """One Identifier carried on the request body."""

    scheme: str = Field(..., min_length=1, max_length=50)
    value: str = Field(..., min_length=1, max_length=200)


class RegisterVisitRequest(BaseModel):
    """Body for `POST /visits`."""

    visit_id: UUID = Field(
        ...,
        description=(
            "Caller-supplied UUID. BSS subscriber uses deterministic "
            "uuid5; operator-direct may use uuid4."
        ),
    )
    policy_id: UUID = Field(..., description="Policy that scopes this visit's authz.")
    surface_id: UUID = Field(
        ..., description="Surface this visit binds to (e.g., 2-BM endstation)."
    )
    type: VisitType = Field(
        ...,
        description=(
            "Operational nature: user / commissioning / maintenance / calibration / staff."
        ),
    )
    planned_start_at: datetime = Field(..., description="Scheduled start (operator-supplied).")
    planned_end_at: datetime = Field(
        ..., description="Scheduled end; must be strictly after planned_start_at."
    )
    parent_id: UUID | None = Field(
        default=None,
        description=(
            "Optional self-FK for nested commissioning. The decider enforces "
            "parent existence and same-Surface cohesion."
        ),
    )
    external_refs: list[_IdentifierBody] = Field(
        default_factory=list[_IdentifierBody],
        description=(
            "Anti-corruption refs to upstream-deferred concepts (proposal, "
            "btr, visit, cycle). Stored on the event; surfaced through the "
            "list_visits_by_external_ref query slice."
        ),
    )


class RegisterVisitResponse(BaseModel):
    """Response body for `POST /visits`."""

    visit_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.trust.register_visit
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/visits",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterVisitResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (e.g. planned_end_at <= planned_start_at).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Visit with this id already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation OR Idempotency-Key reuse.",
        },
    },
    summary="Register a new Visit on a Surface under a Policy",
)
async def post_visits(
    body: RegisterVisitRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response."
            ),
        ),
    ] = None,
) -> RegisterVisitResponse:
    visit_id = await handler(
        RegisterVisit(
            visit_id=body.visit_id,
            policy_id=body.policy_id,
            surface_id=body.surface_id,
            type=body.type,
            planned_start_at=body.planned_start_at,
            planned_end_at=body.planned_end_at,
            parent_id=body.parent_id,
            external_refs=frozenset(
                Identifier(scheme=r.scheme, value=r.value) for r in body.external_refs
            ),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterVisitResponse(visit_id=visit_id)
