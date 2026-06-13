"""HTTP route for the `stop_run` slice.

Action endpoint at `POST /runs/{run_id}/stop`. Body carries
`reason` (1-500 chars). 204 No Content on success.
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
from cora.run.features.stop_run.command import StopRun
from cora.run.features.stop_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class StopRunRequest(BaseModel):
    """Body for `POST /runs/{run_id}/stop`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the stop (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.stop_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/stop",
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
            "description": "No run exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run is not in `Running` or `Held` status (stop requires "
                "either; stopping a terminal run raises), OR a concurrent "
                "write to the same run stream conflicted (optimistic "
                "concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Controlled early exit of a Run (Running | Held → Stopped)",
)
async def post_runs_stop(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    body: StopRunRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        StopRun(run_id=run_id, reason=body.reason),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
