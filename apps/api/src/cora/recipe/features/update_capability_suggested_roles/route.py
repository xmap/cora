"""HTTP route for `update_capability_suggested_roles`.

Action endpoint at `POST /capabilities/{capability_id}/suggested-roles`.
Sub-resource action style mirrors the shipped
`update_method_parameters_schema` precedent (POST, not PUT, per the
CORA action-endpoint convention).
"""

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
from cora.recipe.features.update_capability_suggested_roles.command import (
    UpdateCapabilitySuggestedRoles,
)
from cora.recipe.features.update_capability_suggested_roles.handler import Handler


class UpdateCapabilitySuggestedRolesRequest(BaseModel):
    """Body for `POST /capabilities/{capability_id}/suggested-roles`."""

    suggested_role_ids: list[UUID] = Field(
        ...,
        description=(
            "FULL replacement set of global Role contract ids the "
            "operator suggests this Capability is naturally satisfied "
            "by (Layer 3 sub-slice 3E; documentation-only per memo "
            "Lock 10). Each role_id is verified to resolve via the "
            "Role projection at the handler edge. Empty list clears "
            "the set. Deduplicated server-side."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.update_capability_suggested_roles
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/capabilities/{capability_id}/suggested-roles",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Capability exists with the given id, OR one or "
                "more supplied role_ids do not resolve to a "
                "registered Role (handler-side RoleLookup precondition)."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Capability is Deprecated; suggested_role_ids updates "
                "require Defined or Versioned status."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Author the editorial suggested_role_ids set on a Capability",
)
async def post_capabilities_suggested_roles(
    capability_id: Annotated[UUID, Path(description="Target Capability's id.")],
    body: UpdateCapabilitySuggestedRolesRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        UpdateCapabilitySuggestedRoles(
            capability_id=capability_id,
            suggested_role_ids=frozenset(body.suggested_role_ids),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
