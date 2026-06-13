"""HTTP route for the `deprecate_assembly` slice.

Action endpoint at `POST /assemblies/{assembly_id}/deprecate`.
Body carries the operator-supplied `reason` (audit-log breadcrumb).
204 No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.deprecate_assembly.command import DeprecateAssembly
from cora.equipment.features.deprecate_assembly.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH


class DeprecateAssemblyRequest(BaseModel):
    """Body for `POST /assemblies/{assembly_id}/deprecate`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the deprecation (audit-log "
            "breadcrumb). REQUIRED. Mirrors decommission_mount's "
            "reason field shape."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.deprecate_assembly
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assemblies/{assembly_id}/deprecate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No assembly exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Assembly is not in `Defined` or `Versioned` status "
                "(deprecate requires one of those; re-deprecating a "
                "Deprecated Assembly raises), OR a concurrent write "
                "to the same Assembly stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Request body failed schema validation.",
        },
    },
    summary="Mark an existing Assembly as deprecated (terminal)",
)
async def post_assemblies_deprecate(
    assembly_id: Annotated[UUID, Path(description="Target Assembly's id.")],
    body: DeprecateAssemblyRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DeprecateAssembly(assembly_id=assembly_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
