"""HTTP route for the `define_policy` slice.

Pydantic request/response schemas + APIRouter for `POST /policies`.
The slice's BC-level wiring (`cora.trust.routes.register_trust_routes`)
includes this router on the FastAPI app.

Permission sets arrive as JSON arrays (`list[UUID]` / `list[str]`)
and are converted to `frozenset` before constructing the
`DefinePolicy` command. Pydantic validates UUIDs but does NOT
verify the referenced Conduit / Actors exist — eventual-consistency
stance documented on the Policy aggregate.
"""

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
from cora.trust.aggregates.policy import POLICY_NAME_MAX_LENGTH
from cora.trust.features.define_policy.command import DefinePolicy
from cora.trust.features.define_policy.handler import IdempotentHandler


class DefinePolicyRequest(BaseModel):
    """Body for `POST /policies`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=POLICY_NAME_MAX_LENGTH,
        description="Display name for the new policy.",
    )
    conduit_id: UUID = Field(
        ...,
        description=("UUID of the Conduit this policy governs (not validated for existence)."),
    )
    permitted_principal_ids: list[UUID] = Field(
        ...,
        description=(
            "Principals (UUIDs) allowed to act via this conduit. "
            "Empty list yields a deny-all policy."
        ),
    )
    permitted_commands: list[str] = Field(
        ...,
        description=(
            "Command names (for example 'RegisterActor', 'DefineZone') allowed via this "
            "conduit. Empty list yields a deny-all policy."
        ),
    )
    surface_id: UUID = Field(
        description=(
            "UUID of the Surface this policy governs. Required: every "
            "policy binds a concrete Surface seeded by the deployment. "
            "The nil sentinel is rejected (InvalidPolicySurfaceError); "
            "it survives only on the retired V1 bootstrap seed stream."
        ),
    )


class DefinePolicyResponse(BaseModel):
    """Response body for `POST /policies`."""

    policy_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.trust.define_policy
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/policies",
    status_code=status.HTTP_201_CREATED,
    response_model=DefinePolicyResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Define a new authorization Policy for a Conduit",
)
async def post_policies(
    body: DefinePolicyRequest,
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
                "response instead of re-creating the policy."
            ),
        ),
    ] = None,
) -> DefinePolicyResponse:
    policy_id = await handler(
        DefinePolicy(
            name=body.name,
            conduit_id=body.conduit_id,
            permitted_principal_ids=frozenset(body.permitted_principal_ids),
            permitted_commands=frozenset(body.permitted_commands),
            surface_id=body.surface_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefinePolicyResponse(policy_id=policy_id)
