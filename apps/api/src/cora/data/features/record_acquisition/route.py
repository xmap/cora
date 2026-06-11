"""HTTP route for the `record_acquisition` slice.

`POST /acquisitions` returns 201 + RecordAcquisitionResponse on
success. The body carries the three cross-aggregate bindings
(dataset_id, producing_asset_id, the optional producing_run_id), the
instrument wall-clock captured_at, and the two carrier dicts
(settings, evidence). `acquisition_id` is minted by the handler;
`occurred_at` is stamped from the Clock port.

Flat route (not nested under any parent): an Acquisition spans three
aggregates (Asset + Run + Dataset) and is not naturally nested under
any one of them.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.features.record_acquisition.command import RecordAcquisition
from cora.data.features.record_acquisition.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class RecordAcquisitionRequest(BaseModel):
    """Body for `POST /acquisitions`."""

    dataset_id: UUID = Field(
        ...,
        description="Id of the logical Dataset this capture produced.",
    )
    producing_asset_id: UUID = Field(
        ...,
        description=(
            "Id of the capturing Asset. Its Family must declare the "
            "Capturing affordance or the request is rejected with 409."
        ),
    )
    captured_at: datetime = Field(
        ...,
        description=(
            "Instrument wall-clock moment the bytes were physically "
            "produced (caller-asserted provenance). May precede the "
            "CORA-side recording time by any amount (backfills are "
            "legitimate); a captured_at in the future beyond the clock-"
            "skew tolerance is rejected with 400."
        ),
    )
    producing_run_id: UUID | None = Field(
        default=None,
        description=(
            "Optional id of the Run context. None for calibration / "
            "dark-field / autonomous-agent standalone captures with no "
            "Run context."
        ),
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Operator / system settings active at capture. Shape-only "
            "validated today (primitive leaves); per-Family schema "
            "validation is a future slice."
        ),
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Capture-specific evidence (freeform placeholder today; "
            "shape-only validated). Per-Family evidence schemas are a "
            "future slice."
        ),
    )

    model_config = {"extra": "forbid"}


class RecordAcquisitionResponse(BaseModel):
    """Response body for `POST /acquisitions`."""

    acquisition_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.record_acquisition
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/acquisitions",
    status_code=status.HTTP_201_CREATED,
    response_model=RecordAcquisitionResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: malformed settings / evidence "
                "shape, or a captured_at in the future beyond the clock-skew "
                "tolerance."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: dataset_id, "
                "producing_asset_id, or producing_run_id."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Business-invariant violation: the producing Asset's Family "
                "does not declare the Capturing affordance, or the minted "
                "Acquisition stream already exists."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Record a new Acquisition",
)
async def post_acquisitions(
    body: RecordAcquisitionRequest,
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
                "response instead of re-recording the Acquisition."
            ),
        ),
    ] = None,
) -> RecordAcquisitionResponse:
    acquisition_id = await handler(
        RecordAcquisition(
            dataset_id=body.dataset_id,
            producing_asset_id=body.producing_asset_id,
            captured_at=body.captured_at,
            producing_run_id=body.producing_run_id,
            settings=body.settings,
            evidence=body.evidence,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RecordAcquisitionResponse(acquisition_id=acquisition_id)
