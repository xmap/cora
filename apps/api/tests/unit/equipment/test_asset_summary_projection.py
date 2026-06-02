"""Unit tests for AssetSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 6
subscribed Asset events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import AssetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ASSET_ID = uuid4()
_PARENT_ID = uuid4()
_OTHER_PARENT_ID = uuid4()
_MODEL_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Asset",
        stream_id=_ASSET_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = AssetSummaryProjection()
    assert proj.name == "proj_equipment_asset_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "AssetRegistered",
            "AssetActivated",
            "AssetDecommissioned",
            "AssetMaintenanceEntered",
            "AssetMaintenanceExited",
            "AssetRelocated",
            "AssetDegraded",
            "AssetFaulted",
            "AssetRestored",
        }
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_capability_events() -> None:
    """Asset<->Family join events belong in a future projection."""
    proj = AssetSummaryProjection()
    assert "AssetFamilyAdded" not in proj.subscribed_event_types
    assert "AssetFamilyRemoved" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_asset_registered_inserts_with_commissioned_lifecycle_and_parent() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "BeamlineEnclosure-32-ID",
            "level": "Unit",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_asset_summary" in sql
    assert "ON CONFLICT (asset_id) DO NOTHING" in sql
    assert "'Commissioned'" in sql
    # 5g-b: condition column also seeded with 'Nominal' default
    assert "'Nominal'" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "BeamlineEnclosure-32-ID"
    assert args.args[3] == "Unit"
    assert args.args[4] == _PARENT_ID
    # drawing trio omitted from payload: all three columns fold to NULL.
    assert args.args[5] is None
    assert args.args[6] is None
    assert args.args[7] is None
    # model_id omitted from payload: column folds to NULL.
    assert args.args[8] is None
    assert args.args[9] == _NOW


@pytest.mark.unit
async def test_asset_registered_with_drawing_backfills_three_columns() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "Microscope-2BM-A",
            "level": "Assembly",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "drawing": {
                "system": "ICMS",
                "number": "P4105",
                "revision": "A",
            },
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[5] == "ICMS"
    assert args.args[6] == "P4105"
    assert args.args[7] == "A"


@pytest.mark.unit
async def test_asset_registered_with_drawing_no_revision_keeps_revision_null() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "Microscope-2BM-A",
            "level": "Assembly",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "drawing": {"system": "EDMS", "number": "9001"},
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[5] == "EDMS"
    assert args.args[6] == "9001"
    assert args.args[7] is None


@pytest.mark.unit
async def test_asset_registered_with_model_id_populates_model_column() -> None:
    """Bound Asset: AssetRegistered payload carries model_id; projection
    parses to UUID and writes into the model_id column."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "Microscope-2BM-A",
            "level": "Assembly",
            "parent_id": str(_PARENT_ID),
            "model_id": str(_MODEL_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[8] == _MODEL_ID


@pytest.mark.unit
async def test_asset_registered_without_model_id_leaves_model_column_null() -> None:
    """Legacy AssetRegistered events (and genesis registrations with no
    Model binding) omit the model_id payload key entirely; the column
    folds to NULL via payload.get('model_id')."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "unbound-asset",
            "level": "Device",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[8] is None


@pytest.mark.unit
async def test_asset_registered_with_null_parent_for_enterprise_root() -> None:
    """Enterprise-level Assets are the root; parent_id is None."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "Argonne",
            "level": "Enterprise",
            "parent_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] == "Enterprise"
    assert args.args[4] is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_lifecycle"),
    [
        ("AssetActivated", "Active"),
        ("AssetDecommissioned", "Decommissioned"),
        ("AssetMaintenanceEntered", "Maintenance"),
        ("AssetMaintenanceExited", "Active"),
    ],
)
async def test_lifecycle_transition_updates_lifecycle_field(
    event_type: str, expected_lifecycle: str
) -> None:
    """Each lifecycle event writes its expected lifecycle string.
    Note that AssetActivated and AssetMaintenanceExited both
    map to 'Active' — the projection collapses both to the same
    state since the audit history of "how did we get here?" lives
    in the events themselves."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        event_type,
        {"asset_id": str(_ASSET_ID), "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET lifecycle =" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == expected_lifecycle


@pytest.mark.unit
async def test_asset_relocated_updates_parent_to_to_parent() -> None:
    """Hierarchy mutation: parent_id moves to_parent_id (the from
    side is in the audit trail, not needed in the projection)."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRelocated",
        {
            "asset_id": str(_ASSET_ID),
            "from_parent_id": str(_PARENT_ID),
            "to_parent_id": str(_OTHER_PARENT_ID),
            "reason": "moved to new building",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET parent_id =" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == _OTHER_PARENT_ID


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_asset_capability_added_is_silently_dropped() -> None:
    """AssetFamilyAdded is intentionally NOT in subscribed_event_types
    (belongs in a future asset_capabilities join projection). If the
    SQL filter ever lets one through, the bare match drops it."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored("AssetFamilyAdded", {"asset_id": str(_ASSET_ID)})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


# ---------- condition transitions ----------


@pytest.mark.unit
async def test_asset_degraded_updates_condition_to_degraded() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetDegraded",
        {"asset_id": str(_ASSET_ID), "reason": "hot pixel", "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET condition = $2" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "Degraded"


@pytest.mark.unit
async def test_asset_faulted_updates_condition_to_faulted() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetFaulted",
        {"asset_id": str(_ASSET_ID), "reason": "seized", "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "Faulted"


@pytest.mark.unit
async def test_asset_restored_updates_condition_to_nominal() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRestored",
        {"asset_id": str(_ASSET_ID), "reason": "repaired", "occurred_at": _NOW.isoformat()},
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "Nominal"


@pytest.mark.unit
async def test_condition_event_does_not_carry_reason_into_sql_args() -> None:
    """Reason is audit metadata on the event payload, NOT projected
    into the summary table (a future logbook would carry it). Pin so
    a regression doesn't accidentally start storing reasons in the
    summary row."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetDegraded",
        {
            "asset_id": str(_ASSET_ID),
            "reason": "long detailed reason that should not appear in args",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert "long detailed reason" not in str(args.args)
