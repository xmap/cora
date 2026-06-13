"""HTTP route for the `discard_subject` slice.

Action endpoint at `POST /subjects/{subject_id}/discard`. Same
action-endpoint pattern as the other terminal disposition slices
(return / store). Body carries `reason` (1-500 chars). 204 No
Content on success.
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
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.handler import Handler


class DiscardSubjectRequest(BaseModel):
    """Body for `POST /subjects/{subject_id}/discard`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the discard (1-500 chars after trimming). "
            "Captured verbatim for GDPR + sample-handling audit. Today the "
            "field is unstructured; structured taxonomy is future-additive on "
            "the same triggers as DatasetDiscarded / RunStopped reasons."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.subject.discard_subject
    return handler


router = APIRouter(tags=["subject"])


@router.post(
    "/subjects/{subject_id}/discard",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated: whitespace-only reason.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No subject exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Subject is not in `Removed` state (discard requires Removed), "
                "OR a concurrent write to the same subject stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Destroy / discard an existing (Removed) subject",
)
async def post_subjects_discard(
    subject_id: Annotated[UUID, Path(description="Target subject's id.")],
    body: DiscardSubjectRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        DiscardSubject(subject_id=subject_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
