"""HTTP route for the `truncate_run` slice.

Action endpoint at `POST /runs/{run_id}/truncate`. Body carries
`reason` (1-500 chars) plus optional `interrupted_at` (operator's
best guess at when the actual interruption occurred). 204 No
Content on success.
"""

from datetime import datetime
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
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.features.truncate_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class TruncateRunRequest(BaseModel):
    """Body for `POST /runs/{run_id}/truncate`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the truncation (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive on the same triggers as RunStopped/RunAborted."
        ),
    )
    interrupted_at: datetime | None = Field(
        default=None,
        description=(
            "Operator's best guess at when the actual interruption occurred "
            "(ISO-8601, timezone-aware). Distinct from when the truncate "
            "command itself runs (the system records that as occurred_at). "
            "Optional; null when unknown. Must not be in the future, the "
            "decider rejects future timestamps."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.truncate_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/truncate",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only reason, OR "
                "interrupted_at is in the future relative to now."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No run exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run is not in `Running` or `Held` status (truncate requires "
                "either; truncating a terminal run raises), OR a concurrent "
                "write to the same run stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Cleanup terminal of an interrupted Run (Running | Held → Truncated)",
)
async def post_runs_truncate(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    body: TruncateRunRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        TruncateRun(
            run_id=run_id,
            reason=body.reason,
            interrupted_at=body.interrupted_at,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
