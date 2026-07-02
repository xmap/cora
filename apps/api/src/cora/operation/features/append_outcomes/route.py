"""HTTP route for the `append_outcomes` slice.

`POST /procedures/{procedure_id}/outcomes` returns 200 OK with
`{"event_count": N}` on success. The conductor is the primary caller (one
outcome per steered iteration), but the slice ships the wire surface like
every other slice so an operator or tool can append/audit the same path
uniformly. Producer supplies UUIDv7 event_ids per entry; the store dedups
silently via the Postgres PK.

## Response shape: 200 + event_count is the locked contract

Same posture as `append_diagnostics`: no per-entry failure modes warrant 207
partial-success. Pydantic catches structural errors at the boundary (422 for
the whole batch); Postgres `ON CONFLICT (event_id) DO NOTHING` handles dedup.

## measurements shape NOT enforced at the API today

`measurements` is `list[dict[str, Any]]` at the route level: the list of
Measurement dicts (value / kind / quality / name / units) the pass produced.
The measurement shape is beamline-specific, deliberately not schema-
constrained, so a different beamline's measurement set needs no migration.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.features.append_outcomes.command import (
    AppendProcedureOutcomes,
    OutcomeInput,
)
from cora.operation.features.append_outcomes.handler import Handler

_PROCEDURE_OUTCOME_BATCH_MAX = 500
"""Max outcomes per batch. One steered iteration emits one outcome, so batches
are normally length-1; the cap guards a pathological bulk import."""


class ProcedureOutcomeRequest(BaseModel):
    """One outcome entry's input payload."""

    event_id: UUID = Field(
        ...,
        description=(
            "Producer-supplied UUIDv7 entry id. Idempotency / dedup key; "
            "re-issuing the same id is a silent no-op."
        ),
    )
    iteration_index: int = Field(
        ...,
        ge=0,
        description=(
            "The steered-conduct pass this outcome records; the ascending order "
            "key for resume reconstruction and an audit cross-reference to the "
            "ProcedureIterationEnded of the same pass."
        ),
    )
    point: dict[str, Any] = Field(
        ...,
        description=(
            "The coordinate map the pass measured at (the x), keyed by steering "
            "axis name. Carried on the row so a resume rebuilds the observation "
            "without a join to the iteration event's advised_next_point."
        ),
    )
    measurements: list[dict[str, Any]] = Field(
        ...,
        description=(
            "The measured values the pass produced (the y): a list of Measurement "
            "dicts (value / kind / quality / name / units). Beamline-specific "
            "shape, not schema-constrained so a different measurement set needs "
            "no migration."
        ),
    )
    succeeded: bool = Field(
        ...,
        description="Whether the pass's acquisition succeeded (a failed pass is a real datum).",
    )
    actuation_kind: str | None = Field(
        default=None,
        description="Physical / Simulated / Hybrid provenance of the pass's measurements.",
    )
    sampled_at: datetime = Field(
        ...,
        description=(
            "phenomenonTime (ISO-8601 with timezone): when the pass produced these measurements."
        ),
    )
    occurred_at: datetime | None = Field(
        default=None,
        description=(
            "Optional handler-time override (ISO-8601 with timezone). Defaults "
            "to server clock when omitted."
        ),
    )

    model_config = {"extra": "forbid"}


class AppendProcedureOutcomesRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/outcomes`."""

    entries: list[ProcedureOutcomeRequest] = Field(
        ...,
        min_length=1,
        max_length=_PROCEDURE_OUTCOME_BATCH_MAX,
        description=f"List of outcome entries to append (1-{_PROCEDURE_OUTCOME_BATCH_MAX}).",
    )

    model_config = {"extra": "forbid"}


class AppendProcedureOutcomesResponse(BaseModel):
    """Response body for the append slice."""

    event_count: int = Field(
        ...,
        ge=0,
        description=(
            "Number of entries accepted by the store (includes silently-deduped "
            "retries; producer can re-call with the same event_ids safely)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.append_outcomes
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/outcomes",
    status_code=status.HTTP_200_OK,
    response_model=AppendProcedureOutcomesResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Procedure exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Procedure is not in `Running` (the outcome logbook is "
                "implicitly closed), or a concurrent write to the same "
                "Procedure stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: empty entries list, "
                "batch over cap, or missing required fields."
            ),
        },
    },
    summary=(
        "Append a batch of steered-pass outcomes to a Procedure's outcome "
        "logbook (lazy open-on-first-write)."
    ),
)
async def post_procedures_outcomes(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: AppendProcedureOutcomesRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AppendProcedureOutcomesResponse:
    entries = tuple(
        OutcomeInput(
            event_id=e.event_id,
            iteration_index=e.iteration_index,
            point=dict(e.point),
            measurements=list(e.measurements),
            succeeded=e.succeeded,
            actuation_kind=e.actuation_kind,
            sampled_at=e.sampled_at,
            occurred_at=e.occurred_at,
        )
        for e in body.entries
    )
    count = await handler(
        AppendProcedureOutcomes(procedure_id=procedure_id, entries=entries),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AppendProcedureOutcomesResponse(event_count=count)
