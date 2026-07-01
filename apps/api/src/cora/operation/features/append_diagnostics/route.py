"""HTTP route for the `append_diagnostics` slice.

`POST /procedures/{procedure_id}/diagnostics` returns 200 OK with
`{"event_count": N}` on success. The conductor is the primary caller (one
diagnostic per GP-decided steered iteration), but the slice ships the wire
surface like every other slice so an operator or tool can append/audit the
same path uniformly. Producer supplies UUIDv7 event_ids per entry; the store
dedups silently via the Postgres PK.

## Response shape: 200 + event_count is the locked contract

Same posture as `append_activities`: no per-entry failure modes warrant 207
partial-success. Pydantic catches structural errors at the boundary (422 for
the whole batch); Postgres `ON CONFLICT (event_id) DO NOTHING` handles dedup.

## payload shape NOT enforced at the API today

`payload` is `dict[str, float]` at the route level: the deciding brain's opaque
map of fitted-model summary scalars (lengthscales, noise, acquisition value).
The keys are the adapter's private audit vocabulary, deliberately not schema-
constrained, so a different brain's scalar set needs no migration.
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
from cora.operation.features.append_diagnostics.command import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)
from cora.operation.features.append_diagnostics.handler import Handler

_PROCEDURE_DIAGNOSTIC_BATCH_MAX = 500
"""Max diagnostics per batch. One steered iteration emits one diagnostic, so
batches are normally length-1; the cap guards a pathological bulk import."""


class ProcedureDiagnosticRequest(BaseModel):
    """One diagnostic entry's input payload."""

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
            "The steered-conduct iteration this diagnostic explains; joins to "
            "the same iteration_index on ProcedureIterationEnded."
        ),
    )
    model_ref: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The deciding brain that produced the diagnostics (e.g. 'botorch').",
    )
    payload: dict[str, float] = Field(
        ...,
        description=(
            "The deciding brain's opaque map of fitted-model summary scalars "
            "(per-axis lengthscales, observation noise, acquisition value). "
            "Keys are the adapter's private audit vocabulary; not schema-"
            "constrained so a different brain's scalar set needs no migration."
        ),
    )
    sampled_at: datetime = Field(
        ...,
        description=(
            "phenomenonTime (ISO-8601 with timezone): when the brain produced "
            "the advice this row explains."
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


class AppendProcedureDiagnosticsRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/diagnostics`."""

    entries: list[ProcedureDiagnosticRequest] = Field(
        ...,
        min_length=1,
        max_length=_PROCEDURE_DIAGNOSTIC_BATCH_MAX,
        description=(
            f"List of diagnostic entries to append (1-{_PROCEDURE_DIAGNOSTIC_BATCH_MAX})."
        ),
    )

    model_config = {"extra": "forbid"}


class AppendProcedureDiagnosticsResponse(BaseModel):
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
    handler: Handler = request.app.state.operation.append_diagnostics
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/diagnostics",
    status_code=status.HTTP_200_OK,
    response_model=AppendProcedureDiagnosticsResponse,
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
                "Procedure is not in `Running` (the diagnostics logbook is "
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
        "Append a batch of GP-steering diagnostics to a Procedure's diagnostics "
        "logbook (lazy open-on-first-write)."
    ),
)
async def post_procedures_diagnostics(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: AppendProcedureDiagnosticsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> AppendProcedureDiagnosticsResponse:
    entries = tuple(
        DiagnosticInput(
            event_id=e.event_id,
            iteration_index=e.iteration_index,
            model_ref=e.model_ref,
            payload=e.payload,
            sampled_at=e.sampled_at,
            occurred_at=e.occurred_at,
        )
        for e in body.entries
    )
    count = await handler(
        AppendProcedureDiagnostics(procedure_id=procedure_id, entries=entries),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return AppendProcedureDiagnosticsResponse(event_count=count)
