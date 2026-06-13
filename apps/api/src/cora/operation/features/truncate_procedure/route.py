"""HTTP route for the `truncate_procedure` slice.

Action endpoint at `POST /procedures/{procedure_id}/truncate`. Body
carries `reason` (1-500 chars) plus optional `interrupted_at`
(operator's best guess at when the actual interruption occurred).
204 No Content on success.
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
from cora.operation.features.truncate_procedure.command import TruncateProcedure
from cora.operation.features.truncate_procedure.handler import Handler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class TruncateProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/truncate`."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form reason for the truncation (1-500 chars after trimming). "
            "Today the field is unstructured; structured taxonomy is "
            "future-additive on the same triggers as ProcedureAborted."
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
    handler: Handler = request.app.state.operation.truncate_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/truncate",
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
            "description": "No procedure exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Procedure is not in `Running` status (truncate requires "
                "`Running` today; truncating a `Defined` / `Completed` / "
                "`Aborted` / `Truncated` procedure raises), OR a "
                "concurrent write to the same procedure stream conflicted "
                "(optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Cleanup terminal of an interrupted Procedure (Running -> Truncated)",
)
async def post_procedures_truncate(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: TruncateProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> None:
    await handler(
        TruncateProcedure(
            procedure_id=procedure_id,
            reason=body.reason,
            interrupted_at=body.interrupted_at,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
