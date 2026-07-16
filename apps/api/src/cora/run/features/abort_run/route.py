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
from cora.shared.justification import JUSTIFICATION_MAX_LENGTH
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
    justification: str | None = Field(
        default=None,
        max_length=JUSTIFICATION_MAX_LENGTH,
        description=(
            "Obligation gate (Gate III): AbortRun requires an admission "
            "justification accounting for why this consequential action is "
            "taken. Fail-closed (absent / blank / over-length -> 422). Distinct "
            "from `reason`, which is post-hoc text on the RunAborted event; the "
            "justification is the precondition of admission. Kind-blind (a human "
            "and an agent supply it identically)."
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
            "model": ErrorResponse,
            "description": (
                "Path parameter or request body failed schema validation, OR the "
                "obligation gate (Gate III) refused the abort because no valid "
                "justification was supplied (absent / blank / over-length)."
            ),
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
            justification=body.justification,
            decided_by_decision_id=body.decided_by_decision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
