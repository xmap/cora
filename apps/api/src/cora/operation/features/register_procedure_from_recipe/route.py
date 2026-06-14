"""HTTP route for the `register_procedure_from_recipe` slice.

Pydantic request/response schemas + APIRouter for
`POST /procedures/from-recipe`. The slice's BC-level wiring
(`cora.operation.routes.register_operation_routes`) includes this
router on the FastAPI app.

`target_asset_ids` accepts a list of UUIDs at the API boundary (JSON
arrays don't have set semantics); the handler converts to a tuple
before threading into the command. Empty list is allowed (maps to
empty tuple, valid for facility-envelope procedures that don't act
on a specific Asset).

`bindings` is a free-form JSON object; the keys correspond to the
parameter names declared in the bound Recipe's Capability's
`parameters_schema.properties`. Validated cross-aggregate at the
decider boundary; the API surface does not enforce a schema since
the schema lives on the Capability (cross-BC, loaded at handler time).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
)
from cora.operation.features.register_procedure_from_recipe.command import (
    RegisterProcedureFromRecipe,
)
from cora.operation.features.register_procedure_from_recipe.handler import (
    IdempotentHandler,
)


class RegisterProcedureFromRecipeRequest(BaseModel):
    """Body for `POST /procedures/from-recipe`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=PROCEDURE_NAME_MAX_LENGTH,
        description=(
            "Operator-readable display name for the procedure. Mirrors "
            "register_procedure's name field exactly."
        ),
    )
    kind: str = Field(
        ...,
        min_length=1,
        max_length=PROCEDURE_KIND_MAX_LENGTH,
        description=(
            "Free-form ISA-106 procedure-kind discriminator (bakeout, "
            "calibration, alignment, recovery, etc.). Mirrors "
            "register_procedure's kind field exactly."
        ),
    )
    target_asset_ids: list[UUID] = Field(
        default_factory=list[UUID],
        description=(
            "Asset ids this procedure acts on. May be empty (valid for "
            "facility-envelope procedures). Eventual-consistency: ids "
            "are NOT verified at register time."
        ),
    )
    parent_run_id: UUID | None = Field(
        default=None,
        description=(
            "Optional parent Run binding. None = standalone procedure. "
            "Set = Phase-of-Run procedure."
        ),
    )
    recipe_id: UUID = Field(
        ...,
        description=(
            "Recipe whose templated steps will be expanded into this "
            "Procedure. Loaded cross-BC at handler time; missing -> 404."
        ),
    )
    bindings: dict[str, Any] = Field(
        default_factory=dict[str, Any],
        description=(
            "Operator-supplied parameter values keyed by the parameter "
            "names declared in the bound Recipe's Capability's "
            "parameters_schema. Substituted into BindingRef sentinels at "
            "expansion time. Empty dict valid when the Recipe carries no "
            "BindingRefs."
        ),
    )
    max_consecutive_unconverged_iterations: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional 'patience' cap: max consecutive unconverged "
            "iterations before start_iteration refuses the next one (409). "
            "Resets on a converged iteration. None = no cap."
        ),
    )


class RegisterProcedureFromRecipeResponse(BaseModel):
    """Response body for `POST /procedures/from-recipe`."""

    procedure_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.operation.register_procedure_from_recipe
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/from-recipe",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterProcedureFromRecipeResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated (whitespace-only name or kind)."),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Referenced Recipe does not exist OR Recipe's bound Capability does not exist."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Capability.executor_shapes does not include Procedure "
                "(cross-BC executor-shape guard)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation, OR Recipe's "
                "BindingRefs are stale against the current Capability "
                "parameters_schema, OR operator-supplied bindings did "
                "not validate against the Capability's parameters_schema, "
                "OR the expansion produced more than the configured cap."
            ),
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": (
                "Expansion port returned different results for the same "
                "(steps, bindings) input (server-side determinism bug)."
            ),
        },
    },
    summary="Register a new Procedure by expanding a Recipe with operator bindings",
)
async def post_procedures_from_recipe(
    body: RegisterProcedureFromRecipeRequest,
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
                "response instead of re-creating the procedure."
            ),
        ),
    ] = None,
) -> RegisterProcedureFromRecipeResponse:
    procedure_id = await handler(
        RegisterProcedureFromRecipe(
            name=body.name,
            kind=body.kind,
            target_asset_ids=tuple(body.target_asset_ids),
            parent_run_id=body.parent_run_id,
            recipe_id=body.recipe_id,
            bindings=dict(body.bindings),
            max_consecutive_unconverged_iterations=body.max_consecutive_unconverged_iterations,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterProcedureFromRecipeResponse(procedure_id=procedure_id)
