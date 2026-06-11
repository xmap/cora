"""HTTP route for the `remove_family_presents_as` slice.

Action endpoint at `POST /families/{family_id}/remove-presents-as`.
Body carries `role_id`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.remove_family_presents_as.command import (
    RemoveFamilyPresentsAs,
)
from cora.equipment.features.remove_family_presents_as.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RemoveFamilyPresentsAsRequest(BaseModel):
    """Body for `POST /families/{family_id}/remove-presents-as`."""

    role_id: UUID = Field(
        ...,
        description=(
            "Global Role contract id to withdraw from the Family's "
            "presents_as set. Strict-not-idempotent: removing a "
            "Role the Family does not advertise raises."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.remove_family_presents_as
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/families/{family_id}/remove-presents-as",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Family exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "role_id is not in the Family's presents_as set "
                "(strict-not-idempotent), OR a concurrent write to "
                "the same Family stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Remove a global Role contract from a Family's presents_as set",
)
async def post_families_remove_presents_as(
    family_id: Annotated[UUID, Path(description="Target Family's id.")],
    body: RemoveFamilyPresentsAsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        RemoveFamilyPresentsAs(family_id=family_id, role_id=body.role_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
