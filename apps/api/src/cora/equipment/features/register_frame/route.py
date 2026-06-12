"""HTTP route for the `register_frame` slice.

Pydantic request/response schemas + APIRouter for `POST /frames`.

The Placement value object is a dataclass at the domain layer
(`cora.equipment.aggregates._placement`); the shared
`PlacementBody` Pydantic mirror (`cora.equipment._bodies._placement_body`)
is the wire format. The route converts to the domain VO inside the
handler. The conversion is trivial (field-for-field) and raises
`InvalidPlacementError` on domain-rule violations (negative
tolerance, etc.), which the BC's exception handler maps to 400.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.equipment._bodies import PlacementBody
from cora.equipment.aggregates.frame import FRAME_NAME_MAX_LENGTH
from cora.equipment.features.register_frame.command import RegisterFrame
from cora.equipment.features.register_frame.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RegisterFrameRequest(BaseModel):
    """Body for `POST /frames`.

    Root frames pass `parent_id=null` AND
    `placement=null`. Child frames pass both
    non-null, and the embedded `placement.parent_frame_id` must equal
    `parent_id` (decider enforces this with
    InvalidFrameRootError -> 400).
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=FRAME_NAME_MAX_LENGTH,
        description="Display name for the new frame.",
    )
    parent_id: UUID | None = Field(
        ...,
        description=(
            "Immediate parent in the frame tree. Must be null for "
            "root frames; required for all others. Goes together "
            "with placement (both null or both "
            "non-null)."
        ),
    )
    placement: PlacementBody | None = Field(
        ...,
        description=(
            "Pose of this frame's origin relative to its parent. "
            "Must be null for root frames; required for child frames "
            "and must reference parent_id."
        ),
    )


class RegisterFrameResponse(BaseModel):
    """Response body for `POST /frames`."""

    frame_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.equipment.register_frame
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/frames",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterFrameResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name, "
                "negative tolerance, OR root-vs-child mismatch "
                "(parent_id and placement "
                "must be both null or both non-null, and "
                "placement.parent_frame_id must equal parent_id)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing fields, "
                "malformed UUID, negative tolerance via Pydantic ge=0) "
                "OR Idempotency-Key was reused with a different body."
            ),
        },
    },
    summary="Register a new coordinate frame",
)
async def post_frames(
    body: RegisterFrameRequest,
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
                "response instead of re-creating the frame."
            ),
        ),
    ] = None,
) -> RegisterFrameResponse:
    placement = body.placement.to_domain() if body.placement is not None else None
    frame_id = await handler(
        RegisterFrame(
            name=body.name,
            parent_id=body.parent_id,
            placement=placement,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterFrameResponse(frame_id=frame_id)
