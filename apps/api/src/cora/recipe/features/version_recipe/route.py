"""HTTP route for the `version_recipe` slice."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.recipe import (
    RECIPE_VERSION_TAG_MAX_LENGTH,
    steps_from_dict,
)
from cora.recipe.features.version_recipe.command import VersionRecipe
from cora.recipe.features.version_recipe.handler import Handler


class VersionRecipeRequest(BaseModel):
    """Body for `POST /recipes/{recipe_id}/version`."""

    version_tag: str = Field(
        ...,
        min_length=1,
        max_length=RECIPE_VERSION_TAG_MAX_LENGTH,
        description=(
            "Operator-supplied label for this revision (for example "
            "'v2', '2026-Q3'). Free text; institution-specific. NOT "
            "constrained UNIQUE across versions; same tag + same steps "
            "re-emits the event as a re-attestation audit signal."
        ),
    )
    steps: dict[str, Any] = Field(
        ...,
        description=(
            "Replacement step sequence for the new version (wholesale "
            "replace; the prior steps are dropped). BindingRef sentinels "
            "are re-validated against the CURRENT Capability.parameters_schema."
        ),
    )
    closing_steps: dict[str, Any] = Field(
        default_factory=lambda: {"steps": []},
        description=(
            "Replacement closing-step sequence, same shape as `steps` "
            "(wholesale replace alongside it). Empty by default."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.version_recipe
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/recipes/{recipe_id}/version",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only version_tag, empty steps)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Recipe exists with the given id OR referenced Capability does not exist."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Recipe is currently Deprecated.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema validation OR "
                "BindingRef in steps references a parameter not declared "
                "in the current Capability.parameters_schema."
            ),
        },
    },
    summary="Issue a new version label + replacement steps for a Recipe",
)
async def post_recipes_version(
    recipe_id: Annotated[UUID, Path(description="Target Recipe's id.")],
    body: VersionRecipeRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        VersionRecipe(
            recipe_id=recipe_id,
            version_tag=body.version_tag,
            steps=steps_from_dict(body.steps),
            closing_steps=steps_from_dict(body.closing_steps),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
