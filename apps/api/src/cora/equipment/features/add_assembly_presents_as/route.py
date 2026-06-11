"""HTTP route for the `add_assembly_presents_as` slice.

Action endpoint at `POST /assemblies/{assembly_id}/add-presents-as`.
Body carries `role_id`. 204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.add_assembly_presents_as.command import AddAssemblyPresentsAs
from cora.equipment.features.add_assembly_presents_as.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class AddAssemblyPresentsAsRequest(BaseModel):
    """Body for `POST /assemblies/{assembly_id}/add-presents-as`."""

    role_id: UUID = Field(
        ...,
        description=(
            "Global Role contract id to add to the Assembly's "
            "presents_as set. Existence is verified at the handler "
            "edge against the read-side Role projection. The "
            "affordance-superset gate is NOT enforced at template "
            "time; satisfaction lands at register_fixture layer."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.add_assembly_presents_as
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assemblies/{assembly_id}/add-presents-as",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "No Assembly exists with the given id, OR no Role exists with the supplied role_id."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "role_id is already in the Assembly's presents_as set "
                "(strict-not-idempotent), OR a concurrent write to "
                "the same Assembly stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Add a global Role contract to an Assembly's presents_as set",
)
async def post_assemblies_add_presents_as(
    assembly_id: Annotated[UUID, Path(description="Target Assembly's id.")],
    body: AddAssemblyPresentsAsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AddAssemblyPresentsAs(assembly_id=assembly_id, role_id=body.role_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
