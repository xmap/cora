"""HTTP route for the `adjust_run` slice.

Action endpoint at `POST /runs/{run_id}/adjust`. Body carries
`parameters_patch`, `reason`, and optional `decided_by_decision_id`.
Idempotency-Key header is honored (the slice is idempotency-wrapped
at wire.py per the create-style retry-safe convention; operator
retries on flaky network must NOT double-apply patches).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.handler import IdempotentHandler
from cora.shared.text_bounds import REASON_MAX_LENGTH


class AdjustRunRequest(BaseModel):
    """Body for `POST /runs/{run_id}/adjust`."""

    parameters_patch: dict[str, Any] = Field(
        ...,
        description=(
            "RFC 7396 JSON Merge Patch on top of the Run's current "
            "`effective_parameters`. The post-merge result is validated "
            "against the owning Method's `parameters_schema` (when the "
            "Method declares one). Must be non-empty (empty patches "
            "rejected with 400; they would silently no-op and mislead "
            "the audit)."
        ),
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=REASON_MAX_LENGTH,
        description=(
            "Free-form justification (1-500 chars after trimming). "
            "Required: steering without recorded intent is the "
            "abort+restart anti-pattern relocated. Today the field is "
            "unstructured; structured taxonomy is future-additive on "
            "the same triggers as RunAbortReason."
        ),
    )
    decided_by_decision_id: UUID | None = Field(
        default=None,
        description=(
            "Optional Decision id that justified this adjustment. Maps "
            "to `prov:wasInformedBy` at the future PROV-O export "
            "adapter (same export contract used by Decision.parent_id). "
            "NOT verified at the write path (eventual-consistency "
            "stance per cross-BC reference precedent). Operators can "
            "record ad-hoc adjustments without a Decision."
        ),
    )


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.run.adjust_run
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/adjust",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: empty parameters_patch, "
                "whitespace-only reason, or post-merge effective set "
                "fails the Method's parameters_schema."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Referenced Run (or its upstream Plan / Practice / "
                "Method via the Recipe chain) does not exist."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run is not in Running or Held (adjust requires an "
                "in-progress Run; Idle / terminal states are rejected), "
                "OR a concurrent write to the same Run stream "
                "conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Path parameter or request body failed schema "
                "validation OR Idempotency-Key was reused with a "
                "different request body."
            ),
        },
    },
    summary="Adjust a Run's effective parameters mid-flight",
)
async def post_runs_adjust(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    body: AdjustRunRequest,
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
                "response instead of re-applying the patch."
            ),
        ),
    ] = None,
) -> None:
    await handler(
        AdjustRun(
            run_id=run_id,
            parameters_patch=body.parameters_patch,
            reason=body.reason,
            decided_by_decision_id=body.decided_by_decision_id,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
