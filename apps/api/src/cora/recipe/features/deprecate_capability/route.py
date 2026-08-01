"""HTTP route for the `deprecate_capability` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.features.deprecate_capability.command import DeprecateCapability
from cora.recipe.features.deprecate_capability.handler import Handler
from cora.shared.deprecation import DeprecationReason


class DeprecateCapabilityRequest(BaseModel):
    """Body for `POST /capabilities/{capability_id}/deprecate`.

    Optional `replaced_by_capability_id` pointer for the successor
    Capability. Omit entirely for deprecated-without-replacement.
    """

    reason: DeprecationReason = Field(
        ...,
        description=(
            "Why the template is no longer recommended. `Superseded`: a "
            "newer version replaces it, prior use stands. `Defective`: it "
            "was wrong, prior use is suspect. `Obsolete`: what it targeted "
            "no longer exists."
        ),
    )
    replaced_by_capability_id: UUID | None = Field(
        default=None,
        description=(
            "Optional pointer to a successor Capability (LOINC `MAP_TO` "
            "precedent). None means deprecated-without-replacement."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.deprecate_capability
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/capabilities/{capability_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Capability exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Capability is already Deprecated.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Deprecate an existing Capability",
)
async def post_capabilities_deprecate(
    capability_id: Annotated[UUID, Path(description="Target Capability's id.")],
    body: DeprecateCapabilityRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateCapability(
            capability_id=capability_id,
            reason=body.reason,
            replaced_by_capability_id=body.replaced_by_capability_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
