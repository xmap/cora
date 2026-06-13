"""HTTP route for the `mount_subject` slice.

Action endpoint at `POST /subjects/{subject_id}/mount`. Body carries
`asset_id` (the sample-environment Asset to mount onto) and a
required `reason` string (1-500 chars, 4f). 204 No Content on
success.
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
from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.subject.features.mount_subject.command import MountSubject
from cora.subject.features.mount_subject.handler import Handler


class MountSubjectRequest(BaseModel):
    """Body for `POST /subjects/{subject_id}/mount`."""

    asset_id: UUID = Field(
        ...,
        description="Sample-environment Asset id (Equipment.Asset, must be Active).",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the mount (audit-log "
            "breadcrumb). Examples: 'loaded for run #1234', "
            "'calibration mount', 'transport break complete'."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.mount_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects/{subject_id}/mount",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Subject or Asset exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Subject is not in `Received` state (mount requires Received), "
                "OR mount-target Asset is not `Active`, OR a concurrent write "
                "to the same subject stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Mount an existing subject onto a sample-environment Asset",
)
async def post_subjects_mount(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    body: MountSubjectRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        MountSubject(subject_id=subject_id, asset_id=body.asset_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
