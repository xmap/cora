"""HTTP route for the `resume_run` slice.

Action endpoint at `POST /runs/{run_id}/resume`. No body. 204
No Content on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, status

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.aggregates.run import HOLD_CAUSE_OPERATOR
from cora.run.features.resume_run.command import ResumeRun
from cora.run.features.resume_run.handler import Handler


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.resume_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/resume",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
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
                "Run is not in `Held` status (resume requires `Held`; "
                "resuming a `Running` run raises, resuming a terminal run "
                "raises), OR a concurrent write to the same run stream "
                "conflicted (optimistic concurrency)."
            ),
        },
    },
    summary="Resume a held Run (Held → Running)",
)
async def post_runs_resume(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    cause: Annotated[
        str,
        Query(
            description=(
                "Which concern's hold claim this resume discharges. Must match the "
                "cause the hold was placed under. Defaults to `operator`, the routine "
                "case. A Run held by the kill-switch carries `authority-revocation` "
                "and cannot be resumed as `operator`."
            ),
        ),
    ] = HOLD_CAUSE_OPERATOR,
) -> None:
    await handler(
        ResumeRun(run_id=run_id, cause=cause),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
