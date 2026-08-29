"""HTTP route for the `get_recipe` slice.

`GET /recipes/{recipe_id}` returns 200 + RecipeResponse on hit, 404
on miss.

`created_at` / `versioned_at` / `deprecated_at` are sourced from
the `proj_recipe_recipe_summary` projection (Path C). Null semantics
under eventual consistency: read together with `status`. A 200 with
a populated `status` but null timestamp means projection lag, never
a missing transition. A 404 means the Recipe aggregate itself does
not exist.

`steps` is exposed in wire format (the same `{steps: [{kind: ...}]}`
shape `define_recipe` / `version_recipe` accept on input), so
operators can inspect the templated body. `BindingRef` sentinels
serialize as `{__binding__: name}` per the standard wire format.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.recipe import RECIPE_NAME_MAX_LENGTH, steps_to_dict
from cora.recipe.features.get_recipe.handler import Handler
from cora.recipe.features.get_recipe.query import GetRecipe


class RecipeResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. `status` is the StrEnum's
    string value (Defined / Versioned / Deprecated). `version` is
    the operator-supplied label of the most recent `version_recipe`
    call (null until first version). `steps` is the wire-format
    dict (BindingRef sentinels serialize as `{__binding__: name}`).
    `replaced_by_recipe_id` is null on Defined / Versioned /
    Deprecated-without-replacement; populated when a deprecation
    supplied a successor pointer. `created_at` / `versioned_at` /
    `deprecated_at` are projection-sourced lifecycle timestamps
    (Path C); see module docstring for null semantics. `closing_steps`
    mirrors `steps`' wire shape; empty for the common case of a recipe
    with no closing steps.
    """

    id: UUID
    name: str = Field(..., max_length=RECIPE_NAME_MAX_LENGTH)
    capability_id: UUID
    status: str
    version: str | None
    steps: dict[str, Any]
    closing_steps: dict[str, Any]
    replaced_by_recipe_id: UUID | None
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.get_recipe
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/recipes/{recipe_id}",
    status_code=status.HTTP_200_OK,
    response_model=RecipeResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Recipe exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a Recipe by id",
)
async def get_recipes(
    recipe_id: Annotated[UUID, Path(description="Target Recipe's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> RecipeResponse:
    view = await handler(
        GetRecipe(recipe_id=recipe_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe {recipe_id} not found",
        )
    recipe = view.recipe
    timestamps = view.timestamps
    return RecipeResponse(
        id=recipe.id,
        name=recipe.name.value,
        capability_id=recipe.capability_id,
        status=recipe.status.value,
        version=recipe.version,
        steps=steps_to_dict(recipe.steps),
        closing_steps=steps_to_dict(recipe.closing_steps),
        replaced_by_recipe_id=recipe.replaced_by_recipe_id,
        created_at=timestamps.created_at if timestamps is not None else None,
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
    )
