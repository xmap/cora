"""HTTP route for the `mint_missing_asset_persistent_ids` slice.

`POST /assets/mint-missing-persistent-ids` sweeps every Asset that lacks a
persistent identifier and mints one for each. Returns 200 OK with a summary
body (scanned + per-asset minted / skipped / failed lists).

## Response code: always 200, outcomes in body

This is an orchestration endpoint, not a CRUD call. Per-asset outcomes (a
mint the authority rejected, an Asset that already had an id, a lost race)
are NORMAL operational results the operator triages, so they land in the
response body, not as HTTP 4xx/5xx. Only auth / validation faults map to
error codes (403 deny, 422 malformed body). Mirrors `conduct_procedure`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from cora.equipment.features.mint_missing_asset_persistent_ids.command import (
    DEFAULT_BATCH_LIMIT,
    MintMissingAssetPersistentIds,
    MintMissingAssetPersistentIdsResult,
)
from cora.equipment.features.mint_missing_asset_persistent_ids.handler import Handler
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.shared.identifier import PersistentIdentifierScheme

_LIMIT_MAX = 1000


class MintMissingAssetPersistentIdsRequest(BaseModel):
    """Body for `POST /assets/mint-missing-persistent-ids`."""

    scheme: PersistentIdentifierScheme = PersistentIdentifierScheme.DOI
    facility_code: str | None = Field(
        default=None,
        description="Scope the sweep to one facility code; omit to sweep all facilities.",
    )
    limit: int = Field(
        default=DEFAULT_BATCH_LIMIT,
        ge=1,
        le=_LIMIT_MAX,
        description=(
            f"Max Assets to mint this call (1-{_LIMIT_MAX}). Bounds external mint "
            "calls; re-run to continue (the sweep is re-run-safe)."
        ),
    )

    model_config = {"extra": "forbid"}


class _MintedAssetResponse(BaseModel):
    asset_id: UUID
    scheme: str
    value: str


class _SkippedAssetResponse(BaseModel):
    asset_id: UUID
    reason: str


class _FailedAssetResponse(BaseModel):
    asset_id: UUID
    error_class: str
    message: str


class MintMissingAssetPersistentIdsResponse(BaseModel):
    """Summary of one bulk-mint sweep. `scanned` is the number of Assets
    enumerated as missing an id; each lands in exactly one of the lists."""

    scanned: int
    minted: list[_MintedAssetResponse]
    skipped: list[_SkippedAssetResponse]
    failed: list[_FailedAssetResponse]


def result_to_wire(
    result: MintMissingAssetPersistentIdsResult,
) -> MintMissingAssetPersistentIdsResponse:
    """Build the wire response from the slice result. Public so `tool.py` reuses it."""
    return MintMissingAssetPersistentIdsResponse(
        scanned=result.scanned,
        minted=[
            _MintedAssetResponse(
                asset_id=m.asset_id,
                scheme=m.persistent_id.scheme.value,
                value=m.persistent_id.value,
            )
            for m in result.minted
        ],
        skipped=[
            _SkippedAssetResponse(asset_id=s.asset_id, reason=s.reason) for s in result.skipped
        ],
        failed=[
            _FailedAssetResponse(asset_id=f.asset_id, error_class=f.error_class, message=f.message)
            for f in result.failed
        ],
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.equipment.mint_missing_asset_persistent_ids
    return handler


router = APIRouter(tags=["equipment"])


@router.post(
    "/assets/mint-missing-persistent-ids",
    status_code=status.HTTP_200_OK,
    response_model=MintMissingAssetPersistentIdsResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize policy denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: scheme outside the "
                "closed enum, limit out of bounds, unknown field."
            ),
        },
    },
    summary="Bulk-mint persistent identifiers for every Asset that lacks one",
)
async def post_assets_mint_missing_persistent_ids(
    body: MintMissingAssetPersistentIdsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> MintMissingAssetPersistentIdsResponse:
    """Sweep + mint. Per-asset outcomes land in the response body."""
    result = await handler(
        MintMissingAssetPersistentIds(
            scheme=body.scheme,
            facility_code=body.facility_code,
            limit=body.limit,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)
