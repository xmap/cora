"""End-to-end: the Asset.owners JSONB column lands in
proj_equipment_asset_summary against real Postgres.

Mirrors the alternate_identifiers integration suite. Pins:

  - AssetRegistered carrying owners writes them sorted by name ASC
  - AssetOwnerAdded appends + re-sorts + dedupes the JSONB array;
    re-replay is a no-op (idempotency pin)
  - AssetOwnerRemoved filters out the matching name; re-replay
    against a row missing that name is a no-op; removing the last
    owner collapses to '[]' (NOT NULL constraint)
  - Concurrent AssetOwnerAdded events produce a consistent JSONB
    array (replay-safe under apply() re-entry)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import NewEvent
from tests.integration._equipment_helpers import drain_equipment_projections

_NOW = datetime(2026, 6, 3, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _append_asset_registered(
    pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    owners: list[dict[str, object]] | None = None,
) -> None:
    """Append a synthetic AssetRegistered event directly to the event
    store and drain projections. Bypasses the register_asset handler
    so the owners payload key can be exercised at the projection
    layer in isolation."""
    store = PostgresEventStore(pool)
    payload: dict[str, object] = {
        "asset_id": str(asset_id),
        "name": "synthetic-asset",
        "tier": "Device",
        "parent_id": str(uuid4()),
        "occurred_at": _NOW.isoformat(),
        "commissioned_by": str(_PRINCIPAL_ID),
    }
    if owners is not None:
        payload["owners"] = owners
    await store.append(
        "Asset",
        asset_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="AssetRegistered",
                schema_version=1,
                payload=payload,
                occurred_at=_NOW,
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                metadata={},
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    await drain_equipment_projections(pool)


async def _append_owner_event(
    pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    expected_version: int,
    event_type: str,
    payload_extra: dict[str, object],
) -> int:
    store = PostgresEventStore(pool)
    payload: dict[str, object] = {
        "asset_id": str(asset_id),
        "occurred_at": _NOW.isoformat(),
        **payload_extra,
    }
    await store.append(
        "Asset",
        asset_id,
        expected_version,
        [
            NewEvent(
                event_id=uuid4(),
                event_type=event_type,
                schema_version=1,
                payload=payload,
                occurred_at=_NOW,
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                metadata={},
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    await drain_equipment_projections(pool)
    return expected_version + 1


@pytest.mark.integration
async def test_owners_round_trip_through_postgres_jsonb_column(
    db_pool: asyncpg.Pool,
) -> None:
    """Register an asset with three owners; the persisted JSONB array
    deserializes back in deterministic name-sorted order."""
    asset_id = uuid4()
    await _append_asset_registered(
        db_pool,
        asset_id=asset_id,
        owners=[
            {"name": "HZB", "contact": None, "identifier": None, "identifier_type": None},
            {"name": "APS", "contact": "ops@aps.gov", "identifier": None, "identifier_type": None},
            {
                "name": "ESRF",
                "contact": None,
                "identifier": "https://ror.org/02d2y0e15",
                "identifier_type": "ROR",
            },
        ],
    )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owners FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    names = [entry["name"] for entry in row["owners"]]
    assert names == ["APS", "ESRF", "HZB"]


@pytest.mark.integration
async def test_asset_registered_without_owners_defaults_to_empty_array(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _append_asset_registered(db_pool, asset_id=asset_id, owners=None)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owners FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["owners"] == [] or row["owners"] == "[]"


@pytest.mark.integration
async def test_concurrent_add_owner_events_produce_consistent_jsonb(
    db_pool: asyncpg.Pool,
) -> None:
    """Two AssetOwnerAdded events appended in sequence land both owners
    in canonical name-sorted order; replay of the second one is a
    no-op (DISTINCT ON dedupes)."""
    asset_id = uuid4()
    await _append_asset_registered(db_pool, asset_id=asset_id, owners=None)
    version = await _append_owner_event(
        db_pool,
        asset_id=asset_id,
        expected_version=1,
        event_type="AssetOwnerAdded",
        payload_extra={
            "owner": {
                "name": "HZB",
                "contact": None,
                "identifier": None,
                "identifier_type": None,
            }
        },
    )
    await _append_owner_event(
        db_pool,
        asset_id=asset_id,
        expected_version=version,
        event_type="AssetOwnerAdded",
        payload_extra={
            "owner": {
                "name": "APS",
                "contact": None,
                "identifier": None,
                "identifier_type": None,
            }
        },
    )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owners FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    names = [entry["name"] for entry in row["owners"]]
    assert names == ["APS", "HZB"]


@pytest.mark.integration
async def test_owner_added_idempotent_under_re_replay(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-applying an AssetOwnerAdded to a row that already has the
    name is a no-op (DISTINCT ON dedupe). Mirrors the alternate-
    identifier idempotency guarantee."""
    from cora.equipment.projections import AssetSummaryProjection
    from cora.infrastructure.ports.event_store import StoredEvent

    asset_id = uuid4()
    await _append_asset_registered(db_pool, asset_id=asset_id, owners=None)
    await _append_owner_event(
        db_pool,
        asset_id=asset_id,
        expected_version=1,
        event_type="AssetOwnerAdded",
        payload_extra={
            "owner": {
                "name": "HZB",
                "contact": "ops@hzb.de",
                "identifier": None,
                "identifier_type": None,
            }
        },
    )
    replay = StoredEvent(
        position=99,
        event_id=uuid4(),
        stream_type="Asset",
        stream_id=asset_id,
        version=2,
        event_type="AssetOwnerAdded",
        schema_version=1,
        payload={
            "asset_id": str(asset_id),
            "owner": {
                "name": "HZB",
                "contact": "ops@hzb.de",
                "identifier": None,
                "identifier_type": None,
            },
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )
    proj = AssetSummaryProjection()
    async with db_pool.acquire() as conn:
        await proj.apply(replay, conn)
        row = await conn.fetchrow(
            "SELECT owners FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    names = [entry["name"] for entry in row["owners"]]
    assert names == ["HZB"]


@pytest.mark.integration
async def test_owner_removed_drops_matching_entry_and_last_removal_collapses_to_empty(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _append_asset_registered(
        db_pool,
        asset_id=asset_id,
        owners=[
            {"name": "HZB", "contact": None, "identifier": None, "identifier_type": None},
            {"name": "APS", "contact": None, "identifier": None, "identifier_type": None},
        ],
    )
    version = await _append_owner_event(
        db_pool,
        asset_id=asset_id,
        expected_version=1,
        event_type="AssetOwnerRemoved",
        payload_extra={"owner_name": "HZB"},
    )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owners FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    names = [entry["name"] for entry in row["owners"]]
    assert names == ["APS"]

    await _append_owner_event(
        db_pool,
        asset_id=asset_id,
        expected_version=version,
        event_type="AssetOwnerRemoved",
        payload_extra={"owner_name": "APS"},
    )
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT owners::text AS payload FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["payload"] == "[]"
