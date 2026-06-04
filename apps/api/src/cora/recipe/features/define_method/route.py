"""HTTP route for the `define_method` slice.

Pydantic request/response schemas + APIRouter for `POST /methods`.
The slice's BC-level wiring (`cora.recipe.routes.register_recipe_routes`)
includes this router on the FastAPI app.

`needed_family_ids` accepts a list of UUIDs at the API boundary
(JSON arrays don't have set semantics); the handler converts to
frozenset before threading into the command. Empty list is allowed
(maps to empty frozenset, which the decider permits — operationally
valid for purely procedural Methods).
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
from cora.recipe.aggregates.method import (
    METHOD_NAME_MAX_LENGTH,
    METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH,
)
from cora.recipe.features.define_method.command import DefineMethod
from cora.recipe.features.define_method.handler import IdempotentHandler


class DefineMethodRequest(BaseModel):
    """Body for `POST /methods`.

    `needed_family_ids` is required (use `[]` for procedural
    Methods that need no specific equipment family). Eventual-
    consistency: each Family id is NOT verified against the
    Family stream; mismatch surfaces at Plan binding.

    `needed_supplies` is optional; defaults to `[]` for
    backward-compat (older clients keep working). Each element is
    a Supply.kind STRING (1-50 chars), NOT a Supply instance UUID.
    Asymmetric vs needed_family_ids by design; see
    [[project_supply_design]] §"Method.needed_supplies consumer"
    for the rationale (Family is TYPE registry,
    Supply is INSTANCE aggregate per facility sharing a `kind` label).
    Eventual-consistency: kind strings are NOT verified against the
    Supply stream; mismatch surfaces at Plan binding.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=METHOD_NAME_MAX_LENGTH,
        description="Display name for the new method.",
    )
    capability_id: UUID = Field(
        ...,
        description=(
            "Universal Capability template (Recipe BC) this Method "
            "realizes as a Method-shaped executor. REQUIRED per "
            "Pattern P. The bound Capability must declare "
            "`Method` in its executor_shapes set; otherwise 409. "
            "Eventual-consistency: the Capability stream is loaded at "
            "handler time, not API-boundary time; a missing stream "
            "surfaces as 404 via CapabilityNotFoundError."
        ),
    )
    needed_family_ids: list[UUID] = Field(
        ...,
        description=(
            "Family ids this Method requires. May be empty. "
            "Eventual-consistency: ids are NOT verified against the "
            "Family stream at decide time; mismatch surfaces at "
            "Plan binding."
        ),
    )
    needed_supplies: list[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=METHOD_NEEDED_SUPPLY_KIND_MAX_LENGTH,
            ),
        ]
    ] = Field(
        default_factory=list,
        description=(
            "Supply.kind strings this Method requires. May be empty. "
            "Each element is a kind label (for example 'PhotonBeam', "
            "'LiquidNitrogen', 'ComputePool'), 1-50 chars. NOT Supply "
            "instance UUIDs; Methods are facility-portable. Eventual-"
            "consistency: kinds are NOT verified against the Supply "
            "stream at decide time; mismatch surfaces at Plan binding."
        ),
    )
    needed_assembly_ids: list[UUID] = Field(
        default_factory=list[UUID],
        description=(
            "Equipment Assembly ids this Method requires (composition "
            "blueprints). May be empty (Method needs only Assets "
            "satisfying needed_family_ids, no specific composition). "
            "Eventual-consistency: ids are NOT verified against the "
            "Assembly stream at decide time; mismatch surfaces at Plan "
            "binding when the picked Assets must include Fixtures "
            "whose assembly_id covers this set."
        ),
    )


class DefineMethodResponse(BaseModel):
    """Response body for `POST /methods`."""

    method_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.recipe.define_method
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineMethodResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (whitespace-only name).",
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
    summary="Define a new abstract technique-class recipe (Method)",
)
async def post_methods(
    body: DefineMethodRequest,
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
                "response instead of re-creating the method."
            ),
        ),
    ] = None,
) -> DefineMethodResponse:
    method_id = await handler(
        DefineMethod(
            name=body.name,
            capability_id=body.capability_id,
            needed_family_ids=frozenset(body.needed_family_ids),
            needed_supplies=frozenset(body.needed_supplies),
            needed_assembly_ids=frozenset(body.needed_assembly_ids),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineMethodResponse(method_id=method_id)
