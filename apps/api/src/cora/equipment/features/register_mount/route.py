"""HTTP route for the `register_mount` slice.

POST /mounts: register a new slot.

Re-uses the shared `PlacementBody` and `DrawingBody` wire shapes;
the route handler converts both to domain VOs before constructing
the command.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import DrawingBody, PlacementBody
from cora.equipment.aggregates.mount import SLOT_CODE_MAX_LENGTH
from cora.equipment.features.register_mount.command import RegisterMount
from cora.equipment.features.register_mount.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegisterMountRequest(BaseModel):
    """Body for `POST /mounts`."""

    slot_code: str = Field(
        ...,
        min_length=1,
        max_length=SLOT_CODE_MAX_LENGTH,
        description=(
            "External alias for this slot (e.g., APS 2-BM RSS tag "
            "'02-BM-A-K-01'). Must be unique across Active mounts."
        ),
    )
    parent_id: UUID | None = Field(
        ...,
        description=(
            "Immediate parent in the slot hierarchy. Null for top-level "
            "slots. Hierarchy axis is distinct from coordinate-frame "
            "axis (which lives on placement.parent_frame_id)."
        ),
    )
    placement: PlacementBody = Field(
        ...,
        description="Pose of this slot relative to a Frame.",
    )
    drawing: DrawingBody | None = Field(
        None,
        description=(
            "Optional engineering reference for the slot itself "
            "(distinct from the installed Asset's build-to drawing)."
        ),
    )


class RegisterMountResponse(BaseModel):
    """Response body for `POST /mounts`."""

    mount_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.register_mount
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/mounts",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterMountResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only slot_code, "
                "non-finite (NaN / Inf) or negative-tolerance Placement "
                "value, or invalid Drawing."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Mount with the requested slot_code already exists (MountAlreadyExistsError)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new mount (slot) in the beamline",
)
async def post_mounts(
    body: RegisterMountRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied key for idempotent retry: replaying the "
                "same key returns the original mount_id without creating a new mount. "
                "Updates, decommission, install, and uninstall slices have no "
                "Idempotency-Key equivalent (the decider is already strict-not-idempotent)."
            ),
        ),
    ] = None,
) -> RegisterMountResponse:
    mount_id = await handler(
        RegisterMount(
            slot_code=body.slot_code,
            parent_id=body.parent_id,
            placement=body.placement.to_domain(),
            drawing=body.drawing.to_domain() if body.drawing is not None else None,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterMountResponse(mount_id=mount_id)
