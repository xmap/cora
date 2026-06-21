"""HTTP route for the `append_observations` slice.

`POST /runs/{run_id}/observations` returns 200 OK with `{"event_count":
N}` on success. Body shape carries a list of polymorphic Reading
entries (discriminated by `sampling_procedure`); producer supplies
UUIDv7 event_ids per entry; the store dedups silently via Postgres PK.

## Response shape: 200 + event_count is the locked contract

Same posture as Decision BC's `append_inferences` for the same reason:
no per-entry failure modes warrant 207 partial-success. Pydantic
catches structural errors at the boundary (422 for the whole batch);
Postgres `ON CONFLICT (event_id) DO NOTHING` handles dedup silently.

## Discriminator values pinned at the API layer

`sampling_procedure` is a closed `Literal["baseline"]` today
(extends to `Literal["baseline", "monitor"]` later). The DDL
column is plain TEXT, extension lands as a code edit, not a
migration, per [[project_run_reading_design]] §Locks.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.features.append_observations.command import (
    AppendObservations,
    ObservationInput,
)
from cora.run.features.append_observations.handler import Handler

_RUN_READING_BATCH_MAX = 500
"""Max observations per batch. Generous enough for DAQ-adapter burst
patterns (a frame's worth of channels in one POST) while small
enough that a single bad batch can't OOM the handler. Larger
batches should split client-side."""


class ObservationRequest(BaseModel):
    """One observation entry's input payload (polymorphic, SOSA-aligned).

    Required: event_id + channel_name + value + sampled_at +
    sampling_procedure. `units` and `occurred_at` are optional.
    """

    event_id: UUID = Field(
        ...,
        description=(
            "Producer-supplied UUIDv7 entry id. Idempotency / dedup "
            "key; re-issuing the same id is a silent no-op."
        ),
    )
    channel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "Sensor or motor identifier (operator-meaningful name; "
            "for example 'T_sample', 'motor_x', 'ring_current')."
        ),
    )
    value: float = Field(
        ...,
        allow_inf_nan=False,
        description="Scalar observation value. NaN and Infinity rejected.",
    )
    sampled_at: datetime = Field(
        ...,
        description=(
            "SOSA phenomenonTime (ISO-8601 with timezone): when the sensor captured the value."
        ),
    )
    sampling_procedure: Literal["baseline", "monitor"] = Field(
        ...,
        description=(
            "SOSA-aligned discriminator. 'baseline' is a snapshot at "
            "run boundary (start / end). 'monitor' is sub-Hz time-"
            "series during the run (Bluesky monitor stream pattern). "
            "Future values land additively (no migration)."
        ),
    )
    units: str | None = Field(
        default=None,
        max_length=64,
        description="Optional unit string (for example 'K', 'mm', 'mA').",
    )
    occurred_at: datetime | None = Field(
        default=None,
        description=(
            "Optional handler-time override (ISO-8601 with timezone). "
            "Defaults to server clock when omitted; producers with "
            "their own ingest-time clock can populate explicitly."
        ),
    )
    is_simulated: bool = Field(
        default=False,
        description=(
            "Provenance flag. True only when a simulator / replay feeder "
            "produced this value; defaults to False (real). Closed-loop "
            "rules disqualify simulated values so they cannot act on them "
            "as if real."
        ),
    )

    model_config = {"extra": "forbid"}


class AppendRunReadingsRequest(BaseModel):
    """Body for `POST /runs/{run_id}/observations`."""

    entries: list[ObservationRequest] = Field(
        ...,
        min_length=1,
        max_length=_RUN_READING_BATCH_MAX,
        description=(f"List of observation entries to append (1-{_RUN_READING_BATCH_MAX})."),
    )

    model_config = {"extra": "forbid"}


class AppendObservationsResponse(BaseModel):
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
    handler: Handler = request.app.state.run.append_observations
    return handler


router = APIRouter(tags=["run"])


@router.post(
    "/runs/{run_id}/observations",
    status_code=status.HTTP_200_OK,
    response_model=AppendObservationsResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Per-entry validation failed in the handler "
                "(InvalidChannelNameError / InvalidObservationValueError / "
                "InvalidSamplingProcedureError)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No Run exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Run is in a terminal status (Completed | Aborted | "
                "Stopped | Truncated); the observation logbook is "
                "implicitly closed."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: empty entries "
                "list, batch over cap, missing required fields, "
                "invalid sampling_procedure value, NaN/Infinity observation "
                "value, channel_name out of bounds."
            ),
        },
    },
    summary=(
        "Append a batch of polymorphic sensor / motor observations to a "
        "Run's observation logbook (lazy open-on-first-write)."
    ),
)
async def post_runs_readings(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    body: AppendRunReadingsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AppendObservationsResponse:
    entries = tuple(
        ObservationInput(
            event_id=e.event_id,
            channel_name=e.channel_name,
            value=e.value,
            sampled_at=e.sampled_at,
            sampling_procedure=e.sampling_procedure,
            units=e.units,
            occurred_at=e.occurred_at,
            is_simulated=e.is_simulated,
        )
        for e in body.entries
    )
    count = await handler(
        AppendObservations(run_id=run_id, entries=entries),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AppendObservationsResponse(event_count=count)
