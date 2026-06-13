"""HTTP route for the `dismount_subject` slice.

Action endpoint at `POST /subjects/{subject_id}/dismount`. Body
carries `reason` (1-500 chars). 204 No Content on success.

Distinct from `POST /subjects/{subject_id}/remove` which is
terminal-leading; this endpoint enables multi-stage workflows by
returning the Subject to `Received` so it can be re-mounted.
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
from cora.subject.features.dismount_subject.command import DismountSubject
from cora.subject.features.dismount_subject.handler import Handler


class DismountSubjectRequest(BaseModel):
    """Body for `POST /subjects/{subject_id}/dismount`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Operator-supplied reason for the dismount (audit-log "
            "breadcrumb). Examples: 'run complete', 'transport "
            "break', 'transferring to detector stage', 'end-of-day'."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.dismount_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects/{subject_id}/dismount",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Subject exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Subject is not in `Mounted` or `Measured` state "
                "(dismount requires the Subject to be currently "
                "mounted), OR a concurrent write to the same Subject "
                "stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Dismount a Subject from its current sample-environment Asset (4f)",
)
async def post_subjects_dismount(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    body: DismountSubjectRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DismountSubject(subject_id=subject_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
