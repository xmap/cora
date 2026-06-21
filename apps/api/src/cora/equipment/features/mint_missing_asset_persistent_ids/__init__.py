"""Vertical slice for the `MintMissingAssetPersistentIds` command.

Operator-facing orchestration entry point: enumerates Assets that lack a
persistent identifier and delegates each to `assign_asset_persistent_id`,
which mints via the `PersistentIdentifierMinter` port
(`StubPersistentIdentifierMinter` today; the production DataCite adapter
when credentials land) and folds through the set-once
decider. Returns a structured result; per-asset outcomes are encoded in the
result, not raised, so a single client code-path covers every outcome.
Re-run-safe: only Assets missing an id are touched.

    from cora.equipment.features import mint_missing_asset_persistent_ids

    cmd = mint_missing_asset_persistent_ids.MintMissingAssetPersistentIds()
    handler = mint_missing_asset_persistent_ids.bind(deps, mint_one=mint_one)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.mint_missing_asset_persistent_ids import tool
from cora.equipment.features.mint_missing_asset_persistent_ids.command import (
    FailedAsset,
    MintedAsset,
    MintMissingAssetPersistentIds,
    MintMissingAssetPersistentIdsResult,
    SkippedAsset,
)
from cora.equipment.features.mint_missing_asset_persistent_ids.handler import (
    Handler,
    MintOne,
    bind,
    mint_for_asset_ids,
)
from cora.equipment.features.mint_missing_asset_persistent_ids.route import router

__all__ = [
    "FailedAsset",
    "Handler",
    "MintMissingAssetPersistentIds",
    "MintMissingAssetPersistentIdsResult",
    "MintOne",
    "MintedAsset",
    "SkippedAsset",
    "bind",
    "mint_for_asset_ids",
    "router",
    "tool",
]
