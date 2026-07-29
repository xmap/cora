"""REST route for the `IngestScan` command.

`POST /scans/ingest`: the one endpoint that turns a finished scan file
into Dataset + Distribution + Acquisition atomically. The body carries
only what the caller knows that the file cannot say; everything else
(name, digest, byte size, frame accounting) is read or computed, so
this request is deliberately smaller than composing the three
registration endpoints by hand, and cannot disagree with the file.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import AwareDatetime, BaseModel, Field

from cora.data.aggregates.dataset import DATASET_URI_MAX_LENGTH
from cora.data.features.ingest_scan.command import IngestScan
from cora.data.features.ingest_scan.handler import IdempotentHandler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class IngestScanRequest(BaseModel):
    """Request body for `POST /scans/ingest`."""

    locator: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_URI_MAX_LENGTH,
        description=(
            "Where the scan file is, as a URI the deployment's scan reader "
            "interprets (file:// against the configured roots today). Also "
            "recorded verbatim as the Dataset uri and the Distribution uri."
        ),
    )
    producing_asset_id: UUID = Field(
        description=("Id of the capturing Asset. Its Family must declare the Capturing affordance.")
    )
    supply_id: UUID = Field(
        description=(
            "Id of the storage Supply holding the file at the locator (must "
            "be a registered Storage-kind Supply)."
        )
    )
    access_protocol: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "How a consumer reaches bytes at this Distribution, for example "
            "'POSIX' for a mounted filesystem path."
        ),
    )
    producing_run_id: UUID | None = Field(
        default=None,
        description=("Optional id of the Run context. Omit for calibration / standalone captures."),
    )
    captured_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "Operator-asserted acquisition time, accepted ONLY when the file "
            "carries no parseable timestamp of its own; a parseable file "
            "value always wins, and supplying both is refused as ambiguous. "
            "Timezone-aware."
        ),
    )


class IngestScanResponse(BaseModel):
    """Response body: the identities the ingest minted."""

    dataset_id: UUID = Field(description="Identifier of the newly registered Dataset.")


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.ingest_scan
    return handler


router = APIRouter(tags=["data"])


@router.post(
    "/scans/ingest",
    status_code=status.HTTP_201_CREATED,
    response_model=IngestScanResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "The file cannot be ingested as commanded: unreadable or "
                "unrecognized bytes, structurally incomplete scan, missing "
                "acquisition timestamp with no captured_at supplied, "
                "captured_at supplied alongside a parseable file timestamp, "
                "the file changed while being read, or a domain field "
                "derived from it failed validation."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: producing_asset_id, "
                "supply_id, or producing_run_id."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "These bytes are already ingested: a Dataset with the same "
                "checksum exists, and its id is named in the detail."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Ingest a finished scan file",
)
async def post_scans_ingest(
    body: IngestScanRequest,
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
                "response instead of re-ingesting."
            ),
        ),
    ] = None,
) -> IngestScanResponse:
    dataset_id = await handler(
        IngestScan(
            locator=body.locator,
            producing_asset_id=body.producing_asset_id,
            supply_id=body.supply_id,
            access_protocol=body.access_protocol,
            producing_run_id=body.producing_run_id,
            captured_at=body.captured_at,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return IngestScanResponse(dataset_id=dataset_id)


__all__ = ["IngestScanRequest", "IngestScanResponse", "router"]
