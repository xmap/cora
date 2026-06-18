"""Application handler for the `mint_missing_asset_persistent_ids` slice.

Thin orchestrator (no decider): enumerates Assets that lack a persistent
identifier from `proj_equipment_asset_summary`, then delegates each to the
existing `assign_asset_persistent_id` handler, which mints via the `DoiMinter`
port and folds through the set-once decider. Mirrors
`operation.conduct_procedure`: per-asset failures are encoded in the result,
not raised, so a single response shape covers every outcome the operator
needs to triage.

## Why no decider

This slice records no events on any single Asset stream directly; the wrapped
`assign_asset_persistent_id` handler is what mints and appends. The slice is
an orchestration entry point, so it has no `decider.py` and is registered in
`_ORCHESTRATION_SLICES` (see tests/architecture/test_slice_contract.py).

## Re-run safety

Enumeration returns only Assets with `persistent_id IS NULL` (and not
Decommissioned), and the per-asset decider rejects already-assigned or
Decommissioned Assets, so re-running the sweep is idempotent: a lost race or a
stale read lands the Asset in `skipped`, never a double mint.

## Authorization scope

`MintMissingAssetPersistentIds` is authorized as its own command. Each
delegated `assign_asset_persistent_id` call ALSO authorizes internally with
its own `AssignAssetPersistentId` action; authorization for the bulk entry
does not imply authorization for the per-asset action, the same discipline
`conduct_procedure` documents.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg has no type stubs; the `_enumerate_missing` pool.fetch result is
# untyped (same pragma the list-query handlers carry).

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetPersistentIdAlreadyAssignedError,
    AssetPersistentIdAssignmentForbiddenError,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.mint_missing_asset_persistent_ids.command import (
    FailedAsset,
    MintedAsset,
    MintMissingAssetPersistentIds,
    MintMissingAssetPersistentIdsResult,
    SkippedAsset,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.list_query import ScalarFilter, build_select, render_filter_fragment
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme

_COMMAND_NAME = "MintMissingAssetPersistentIds"
_TABLE = "proj_equipment_asset_summary"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every mint_missing_asset_persistent_ids handler implements."""

    async def __call__(
        self,
        command: MintMissingAssetPersistentIds,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> MintMissingAssetPersistentIdsResult: ...


class MintOne(Protocol):
    """Per-asset mint delegate injected by the composition root.

    Mints a persistent identifier for one Asset and returns it (or raises a
    domain / authority error). Decouples the orchestrator from the
    `assign_asset_persistent_id` slice: `wire_equipment` bridges this to that
    slice's handler, keeping this slice free of cross-slice imports (slice
    independence).
    """

    async def __call__(
        self,
        asset_id: UUID,
        *,
        scheme: PersistentIdentifierScheme,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None,
        surface_id: UUID,
    ) -> PersistentIdentifier: ...


async def mint_for_asset_ids(
    asset_ids: Sequence[UUID],
    *,
    mint_one: MintOne,
    scheme: PersistentIdentifierScheme,
    principal_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    surface_id: UUID,
) -> MintMissingAssetPersistentIdsResult:
    """Mint a persistent id for each asset id, encoding every outcome.

    Pure-of-IO except the injected `mint_one` delegate, so it is unit-testable
    with a fake delegate and no Postgres. Domain rejections (already assigned,
    decommissioned, not found) become `skipped`; any other error, including
    `PersistentIdentifierMintError` from the authority and optimistic
    concurrency conflicts, becomes `failed`. One failing asset never aborts the
    batch.
    """
    minted: list[MintedAsset] = []
    skipped: list[SkippedAsset] = []
    failed: list[FailedAsset] = []

    for asset_id in asset_ids:
        try:
            persistent_id = await mint_one(
                asset_id,
                scheme=scheme,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                surface_id=surface_id,
            )
        except (
            AssetPersistentIdAlreadyAssignedError,
            AssetPersistentIdAssignmentForbiddenError,
            AssetNotFoundError,
        ) as exc:
            skipped.append(SkippedAsset(asset_id=asset_id, reason=type(exc).__name__))
        except Exception as exc:
            # Batch driver: an external mint failure (PersistentIdentifierMintError)
            # or a concurrency conflict on one Asset must not abort the sweep. The
            # outcome is recorded and retried on the next run.
            failed.append(
                FailedAsset(asset_id=asset_id, error_class=type(exc).__name__, message=str(exc))
            )
        else:
            minted.append(MintedAsset(asset_id=asset_id, persistent_id=persistent_id))

    return MintMissingAssetPersistentIdsResult(
        scanned=len(asset_ids),
        minted=tuple(minted),
        skipped=tuple(skipped),
        failed=tuple(failed),
    )


async def _enumerate_missing(deps: Kernel, *, facility_code: str | None, limit: int) -> list[UUID]:
    """Asset ids with no persistent identifier (excluding Decommissioned).

    Reuses the shared `infrastructure.list_query` composer (`build_select` +
    `render_filter_fragment`) rather than hand-rolling SQL, so there is one
    sargable-composition path in the codebase, not two. The optional facility
    filter is rendered as a `column = $N` fragment (NOT a `$N IS NULL OR ...`
    guard) to stay sargable under a generic plan, exactly as the list-query
    handlers do. This is an enumerate, not a paginated list, so it borrows the
    composer but not the full handler (no cursor, no page). Pool-None
    (in-memory mode) returns empty, like the list-query handlers.

    `$1` is the LIMIT; the lone optional facility filter is `$2`.
    """
    if deps.pool is None:
        _log.info("mint_missing_asset_persistent_ids.no_pool")
        return []

    fragments = ["persistent_id IS NULL", "lifecycle <> 'Decommissioned'"]
    params: list[Any] = [limit]
    if facility_code is not None:
        fragments.append(render_filter_fragment(ScalarFilter("facility_code"), 2))
        params.append(facility_code)
    sql = build_select(
        select_columns="asset_id",
        table=_TABLE,
        active_filter_fragments=fragments,
        time_column="created_at",
        id_column="asset_id",
        cursor_param_start=None,
    )
    async with deps.pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [row["asset_id"] for row in rows]


def bind(deps: Kernel, *, mint_one: MintOne) -> Handler:
    """Build the bulk-mint handler closed over deps + the per-asset mint delegate.

    `mint_one` is the composition-root bridge to `assign_asset_persistent_id`
    (built in `wire_equipment`). The bulk handler enumerates and loops; the
    delegate owns minting + the set-once append.
    """

    async def handler(
        command: MintMissingAssetPersistentIds,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> MintMissingAssetPersistentIdsResult:
        _log.info(
            "mint_missing_asset_persistent_ids.start",
            command_name=_COMMAND_NAME,
            scheme=command.scheme.value,
            facility_code=command.facility_code,
            limit=command.limit,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "mint_missing_asset_persistent_ids.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        asset_ids = await _enumerate_missing(
            deps, facility_code=command.facility_code, limit=command.limit
        )
        result = await mint_for_asset_ids(
            asset_ids,
            mint_one=mint_one,
            scheme=command.scheme,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )

        _log.info(
            "mint_missing_asset_persistent_ids.success",
            command_name=_COMMAND_NAME,
            scanned=result.scanned,
            minted=len(result.minted),
            skipped=len(result.skipped),
            failed=len(result.failed),
            correlation_id=str(correlation_id),
        )
        return result

    return handler
