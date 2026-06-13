"""HTTP route for the `abort_run` slice.

Action endpoint at `POST /runs/{run_id}/abort`. Body carries
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
from cora.run.features.abort_run.command import AbortRun
from cora.run.features.abort_run.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AbortRunRequest(BaseModel):
    """Body for `POST /runs/{run_id}/abort`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the abort (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive."
        ),
    )
    decided_by_decision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional Decision id that justified this abort (most "
            "commonly an OperatorAbortDecision or EquipmentAbortDecision "
            "per RunDebrief's 5-value choice enum). Maps to "
            "`prov:wasInformedBy` at the future PROV-O export adapter. "
            "NOT verified at the write path (eventual-consistency stance). "
            "Operators can record ad-hoc / emergency aborts without a "
            "Decision (Decision→Run linkage)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.abort_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/abort",
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
                "Run is not in `Running` status (abort requires `Running` "
                "today; aborting a `Completed` or `Aborted` run raises), "
                "OR a concurrent write to the same run stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Mark an existing Run as aborted (emergency-exit terminal)",
)
async def post_runs_abort(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    body: AbortRunRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        AbortRun(
            run_id=run_id,
            reason=body.reason,
            decided_by_decision_id=body.decided_by_decision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
