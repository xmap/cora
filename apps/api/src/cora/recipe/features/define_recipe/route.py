"""HTTP route for the `define_recipe` slice."""

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
from cora.recipe.aggregates.recipe import (
    RECIPE_NAME_MAX_LENGTH,
    steps_from_dict,
)
from cora.recipe.features.define_recipe.command import DefineRecipe
from cora.recipe.features.define_recipe.handler import IdempotentHandler


class DefineRecipeRequest(BaseModel):
    """Body for `POST /recipes`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=RECIPE_NAME_MAX_LENGTH,
        description="Display name for the new Recipe.",
    )
    capability_id: UUID = Field(
        ...,
        description=(
            "Capability this Recipe realizes. REQUIRED and IMMUTABLE "
            "across versions; re-binding requires authoring a new Recipe."
        ),
    )
    steps: dict[str, Any] = Field(
        ...,
        description=(
            "Wire-format step sequence: `{steps: [{kind: setpoint|action|"
            "check, ...}]}`. Each `value` or `params[k]` position may carry "
            "`{__binding__: name}` to reference a Capability parameter."
        ),
    )
    closing_steps: dict[str, Any] = Field(
        default_factory=lambda: {"steps": []},
        description=(
            "Optional wire-format closing-step sequence, same shape as "
            "`steps`: `{steps: [...]}`. The Conductor walks these after "
            "`steps` ends on a real terminal (Completed or Aborted), never "
            "on a Held pause. Empty by default; most recipes have none."
        ),
    )


class DefineRecipeResponse(BaseModel):
    """Response body for `POST /recipes`."""

    recipe_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.recipe.define_recipe
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/recipes",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineRecipeResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": ("Domain invariant violated (whitespace-only name, empty steps)."),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Referenced Capability does not exist.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR BindingRef in steps "
                "references a parameter not declared in the Capability's "
                "parameters_schema OR steps contain BindingRefs but the "
                "Capability has no parameters_schema."
            ),
        },
    },
    summary="Define a new Recipe against an existing Capability",
)
async def post_recipes(
    body: DefineRecipeRequest,
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
                "response instead of re-creating the Recipe."
            ),
        ),
    ] = None,
) -> DefineRecipeResponse:
    recipe_id = await handler(
        DefineRecipe(
            name=body.name,
            capability_id=body.capability_id,
            steps=steps_from_dict(body.steps),
            closing_steps=steps_from_dict(body.closing_steps),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineRecipeResponse(recipe_id=recipe_id)
