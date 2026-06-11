"""HTTP route for the `add_family_presents_as` slice.

Action endpoint at `POST /families/{family_id}/add-presents-as`. Body
carries `role_id`. 204 No Content on success. Same action-endpoint
pattern as `add_asset_family`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.add_family_presents_as.command import AddFamilyPresentsAs
from cora.equipment.features.add_family_presents_as.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddFamilyPresentsAsRequest(BaseModel):
    """Body for `POST /families/{family_id}/add-presents-as`."""

    role_id: UUID = Field(
        ...,
        description=(
            "Global Role contract id to add to the Family's "
            "presents_as set. Existence is verified at the handler "
            "edge against the read-side Role projection; the "
            "Family's affordances must superset the Role's "
            "required_affordances or the add is rejected."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_family_presents_as
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/families/{family_id}/add-presents-as",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Family exists with the given id, OR no Role exists with the supplied role_id."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Family cannot present the requested Role (missing "
                "required Affordances), OR the role_id is already "
                "in the Family's presents_as set "
                "(strict-not-idempotent), OR a concurrent write to "
                "the same Family stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Add a global Role contract to a Family's presents_as set",
)
async def post_families_add_presents_as(
    family_id: Annotated[UUID, Path(description="Target Family's id.")],
    body: AddFamilyPresentsAsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddFamilyPresentsAs(family_id=family_id, role_id=body.role_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
