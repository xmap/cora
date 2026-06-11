"""HTTP route for the `define_role` slice.

Pydantic request/response schemas + APIRouter for `POST /roles`. The
slice's BC-level wiring (`cora.equipment.routes`) includes this
router on the FastAPI app.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import (
    ROLE_DOCSTRING_MAX_LENGTH,
    ROLE_NAME_MAX_LENGTH,
    SIGNAL_TYPE_MAX_LENGTH,
)
from cora.equipment.features.define_role.command import DefineRole
from cora.equipment.features.define_role.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class DefineRoleRequest(BaseModel):
    """Body for `POST /roles`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_NAME_MAX_LENGTH,
        description="Display name for the new global Role contract.",
    )
    docstring: str = Field(
        ...,
        min_length=1,
        max_length=ROLE_DOCSTRING_MAX_LENGTH,
        description=(
            "Operator-readable one-paragraph contract explanation. "
            "Surfaced at Method-authoring time when operators pick "
            "among candidate Roles. Required; non-empty after trim."
        ),
    )
    required_affordances: list[Affordance] = Field(
        ...,
        description=(
            "Affordance value strings every satisfying Family MUST "
            "advertise. Deduplicated server-side. Must be disjoint "
            "with optional_affordances."
        ),
    )
    optional_affordances: list[Affordance] = Field(
        ...,
        description=(
            "Affordance value strings a satisfying Family MAY advertise. "
            "Deduplicated server-side. Must be disjoint with "
            "required_affordances."
        ),
    )
    produces: list[str] = Field(
        ...,
        description=(
            "Open-vocabulary SignalType labels satisfying Assets emit "
            "(out-direction port signal_type). Each entry trimmed "
            f"server-side to 1-{SIGNAL_TYPE_MAX_LENGTH} chars; empty "
            "list accepted."
        ),
    )
    consumes: list[str] = Field(
        ...,
        description=(
            "Open-vocabulary SignalType labels satisfying Assets accept "
            "(in-direction port signal_type). Each entry trimmed "
            f"server-side to 1-{SIGNAL_TYPE_MAX_LENGTH} chars; empty "
            "list accepted."
        ),
    )


class DefineRoleResponse(BaseModel):
    """Response body for `POST /roles`."""

    role_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.define_role
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/roles",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineRoleResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name or docstring, "
                "required and optional Affordance sets overlap, or a SignalType "
                "entry is empty or too long."
            ),
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
    summary="Define a new global Role contract",
)
async def post_roles(
    body: DefineRoleRequest,
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
                "response instead of re-creating the Role."
            ),
        ),
    ] = None,
) -> DefineRoleResponse:
    role_id = await handler(
        DefineRole(
            name=body.name,
            docstring=body.docstring,
            required_affordances=frozenset(body.required_affordances),
            optional_affordances=frozenset(body.optional_affordances),
            produces=frozenset(body.produces),
            consumes=frozenset(body.consumes),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineRoleResponse(role_id=role_id)
