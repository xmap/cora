"""End-to-end integration test: remove_asset_alternate_identifier against real Postgres.

Round-trip: register + add + remove leaves the asset back at empty
alternate_identifiers (verified via load_asset fold-on-read).
Mirror of `test_remove_asset_family_handler_postgres.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import (
    AssetCannotAddAlternateIdentifierError,
    AssetTier,
    load_asset,
)
from cora.equipment.features import (
    add_asset_alternate_identifier,
    decommission_asset,
    register_asset,
    remove_asset_alternate_identifier,
)
from cora.equipment.features.add_asset_alternate_identifier import (
    AddAssetAlternateIdentifier,
)
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.remove_asset_alternate_identifier import (
    RemoveAssetAlternateIdentifier,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-00000a1d0b00")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_remove_asset_alternate_identifier_persists_event_and_drops_from_fold(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = UUID("01900000-0000-7000-8000-00000a1d0b01")
    register_event_id = UUID("01900000-0000-7000-8000-00000a1d0b0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000a1d0b0f")
    remove_event_id = UUID("01900000-0000-7000-8000-00000a1d0b10")
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, add_event_id, remove_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM-Camera", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_alternate_identifier.bind(deps)(
        AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_asset_alternate_identifier.bind(deps)(
        RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetAlternateIdentifierAdded",
        "AssetAlternateIdentifierRemoved",
    ]
    removed = events[2]
    assert removed.event_id == remove_event_id
    assert removed.metadata == {"command": "RemoveAssetAlternateIdentifier"}

    # Fold-on-read reconstructs the empty frozenset.
    state = await load_asset(deps.event_store, asset_id)
    assert state is not None
    assert state.alternate_identifiers == frozenset()


@pytest.mark.integration
async def test_remove_asset_alternate_identifier_rejects_when_decommissioned(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end lifecycle guard: a Decommissioned asset rejects
    identifier removals with `AssetCannotAddAlternateIdentifierError`
    (the shared lifecycle-guard class is used by BOTH add and remove);
    no Removed event is appended."""
    asset_id = UUID("01900000-0000-7000-8000-00000a1d0c01")
    register_event_id = UUID("01900000-0000-7000-8000-00000a1d0c0e")
    add_event_id = UUID("01900000-0000-7000-8000-00000a1d0c0f")
    decommission_event_id = UUID("01900000-0000-7000-8000-00000a1d0c10")
    identifier = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="XYZ-001")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[asset_id, register_event_id, add_event_id, decommission_event_id],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM-Camera", tier=AssetTier.DEVICE, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_alternate_identifier.bind(deps)(
        AddAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(AssetCannotAddAlternateIdentifierError):
        await remove_asset_alternate_identifier.bind(deps)(
            RemoveAssetAlternateIdentifier(asset_id=asset_id, alternate_identifier=identifier),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await deps.event_store.load("Asset", asset_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssetRegistered",
        "AssetAlternateIdentifierAdded",
        "AssetDecommissioned",
    ]
