"""HTTP route for the `append_activities` slice.

`POST /procedures/{procedure_id}/activities` returns 200 OK with
`{"event_count": N}` on success. Body shape carries a list of
polymorphic step entries (discriminated by `step_kind`); producer
supplies UUIDv7 event_ids per entry; the store dedups silently via
Postgres PK.

## Response shape: 200 + event_count is the locked contract

Same posture as Run BC's `append_observations` for the same reason: no
per-entry failure modes warrant 207 partial-success. Pydantic catches
structural errors at the boundary (422 for the whole batch); Postgres
`ON CONFLICT (event_id) DO NOTHING` handles dedup silently.

## Discriminator values pinned at the API layer

`step_kind` is a closed `Literal["setpoint", "action", "check"]`.
The DDL column is plain TEXT; future-additive operational
vocabulary lands as a code edit, not a migration, per
[[project_operation_design]] watch item "step_kind StrEnum promotion".

## Per-kind payload shape NOT enforced at the API today

The `payload` field is `dict[str, Any]` at the route level. The 10c
design memo locked the polymorphic-with-discriminator + JSON-payload
pattern to keep the Logbook + Entry shape uniform across BCs and let per-kind
operational vocabulary evolve without migrations. Per-kind Pydantic
discriminator-validated models for the payload body land when the
pilot vocabulary settles (currently a watch item alongside
"step_kind StrEnum promotion").
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
from cora.operation.aggregates.procedure import StepKind
from cora.operation.features.append_activities.command import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities.handler import Handler

_PROCEDURE_STEP_BATCH_MAX = 500
"""Max steps per batch. Generous enough for an EPICS adapter burst
(an alignment with several setpoints + checks in one POST)
while small enough that a single bad batch can't OOM the handler.
Larger batches should split client-side. Mirrors Run BC's reading
batch cap."""


class ProcedureStepRequest(BaseModel):
    """One step entry's input payload (polymorphic, ISA-106-aligned).

    Required: event_id + step_kind + payload + sampled_at.
    `occurred_at` is optional.
    """

    event_id: UUID = Field(
        ...,
        description=(
            "Producer-supplied UUIDv7 entry id. Idempotency / dedup "
            "key; re-issuing the same id is a silent no-op."
        ),
    )
    step_kind: StepKind = Field(
        ...,
        description=(
            "ISA-106-aligned discriminator. 'setpoint' = control-point "
            "change applied. 'action' = discrete operation performed. "
            "'check' = verification recorded. Future values land "
            "additively (no migration). Single source of truth: the "
            "`StepKind` Literal exported from cora.operation.aggregates.procedure."
        ),
    )
    payload: dict[str, Any] = Field(
        ...,
        description=(
            "Kind-specific body. Setpoint: channel + target_value + "
            "units? + ramp_rate?. Action: action_name + params. "
            "Check: channel + passed + expected? + actual? + "
            "tolerance?. Per-kind Pydantic model validation lands "
            "when pilot vocabulary settles (watch item)."
        ),
    )
    sampled_at: datetime = Field(
        ...,
        description=(
            "phenomenonTime (ISO-8601 with timezone): when the step "
            "physically happened in the field."
        ),
    )
    occurred_at: datetime | None = Field(
        default=None,
        description=(
            "Optional handler-time override (ISO-8601 with timezone). "
            "Defaults to server clock when omitted; producers with "
            "their own ingest-time clock can populate explicitly."
        ),
    )

    model_config = {"extra": "forbid"}


class AppendProcedureStepsRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/activities`."""

    entries: list[ProcedureStepRequest] = Field(
        ...,
        min_length=1,
        max_length=_PROCEDURE_STEP_BATCH_MAX,
        description=(f"List of step entries to append (1-{_PROCEDURE_STEP_BATCH_MAX})."),
    )

    model_config = {"extra": "forbid"}


class AppendProcedureActivitiesResponse(BaseModel):
    """Response body for the append slice."""

    event_count: int = Field(
        ...,
        ge=0,
        description=(
            "Number of entries accepted by the store (includes "
            "silently-deduped retries; producer can re-call with the "
            "same event_ids safely)."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.append_activities
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/activities",
    status_code=status.HTTP_200_OK,
    response_model=AppendProcedureActivitiesResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Per-entry validation failed in the handler "
                "(InvalidStepKindError; defensive guard for direct in-"
                "process callers that bypass Pydantic)."
            ),
        },
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
                "Procedure is not in `Running` (Defined hasn't started; "
                "terminals have ended); the steps logbook is implicitly "
                "closed. Or a concurrent write to the same Procedure "
                "stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: empty entries "
                "list, batch over cap, missing required fields, "
                "invalid step_kind value."
            ),
        },
    },
    summary=(
        "Append a batch of polymorphic procedural steps to a Procedure's "
        "steps logbook (lazy open-on-first-write)."
    ),
)
async def post_procedures_steps(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: AppendProcedureStepsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AppendProcedureActivitiesResponse:
    entries = tuple(
        ActivityInput(
            event_id=e.event_id,
            step_kind=e.step_kind,
            payload=e.payload,
            sampled_at=e.sampled_at,
            occurred_at=e.occurred_at,
        )
        for e in body.entries
    )
    count = await handler(
        AppendProcedureActivities(procedure_id=procedure_id, entries=entries),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AppendProcedureActivitiesResponse(event_count=count)
