"""Unit tests for AssetSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 6
subscribed Asset events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.equipment.projections import AssetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

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
            "AssetAlternateIdentifierAdded",
            "AssetAlternateIdentifierRemoved",
            "AssetOwnerAdded",
            "AssetOwnerRemoved",
            "AssetPersistentIdAssigned",
            "AssetAttachedToFixture",
            "AssetDetachedFromFixture",
            "AssetPartitionRuleUpdated",
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
            "commissioned_by": str(_TEST_ACTOR_ID),
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
    # alternate_identifiers omitted from payload: column folds to []
    # (NOT NULL DEFAULT '[]'::jsonb on the column, but the projection
    # writes the canonical empty list so the row's payload is
    # explicit and replays remain deterministic). The asyncpg pool
    # registers a jsonb codec that runs json.dumps on every parameter
    # bound to a jsonb column, so the projection passes a Python list
    # directly instead of a pre-serialized JSON string.
    assert args.args[9] == []
    # owners omitted from payload: column folds to the canonical empty
    # list for the same reasons as alternate_identifiers.
    assert args.args[10] == []
    assert args.args[11] == _NOW


@pytest.mark.unit
async def test_asset_registered_with_drawing_backfills_three_columns() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "Microscope-2BM-A",
            "level": "Component",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
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
            "level": "Component",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
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
            "level": "Component",
            "parent_id": str(_PARENT_ID),
            "model_id": str(_MODEL_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
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
            "commissioned_by": str(_TEST_ACTOR_ID),
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
            "commissioned_by": str(_TEST_ACTOR_ID),
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
    in the events themselves.

    AssetDecommissioned is excluded here: it writes lifecycle AND
    decommissioned_at atomically via a dedicated SQL statement (see
    `test_asset_summary_projection_lifecycle_columns`)."""
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


# ---------- alternate identifiers ----------


@pytest.mark.unit
async def test_asset_registered_with_alternate_identifiers_writes_sorted_list() -> None:
    """AssetRegistered carrying alternate_identifiers in the payload
    serializes to a canonical sorted list of dicts in the new column.
    Sort key is (kind, value); the projection re-sorts defensively so
    a hand-crafted out-of-order payload still lands canonical. The
    asyncpg pool's jsonb codec turns the list into JSON at parameter
    bind time, so the projection passes the Python list directly."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "specimen-with-tags",
            "level": "Device",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            # Intentionally out-of-order to exercise the defensive sort.
            "alternate_identifiers": [
                {"kind": "SerialNumber", "value": "SN-002"},
                {"kind": "InventoryNumber", "value": "ANL-12345"},
                {"kind": "SerialNumber", "value": "SN-001"},
            ],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[9] == [
        {"kind": "InventoryNumber", "value": "ANL-12345"},
        {"kind": "SerialNumber", "value": "SN-001"},
        {"kind": "SerialNumber", "value": "SN-002"},
    ]


@pytest.mark.unit
async def test_asset_registered_with_empty_alternate_identifiers_writes_empty_list() -> None:
    """An explicit empty list in the payload still serializes to the
    canonical empty Python list (matches the omit-the-key branch)."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "specimen",
            "level": "Device",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
            "alternate_identifiers": [],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[9] == []


@pytest.mark.unit
async def test_alternate_identifier_added_updates_jsonb_column() -> None:
    """The Added event triggers a JSONB-array UPDATE that appends the
    (kind, value) pair into the alternate_identifiers column. Dedupe +
    re-sort happen server-side via the SQL statement; the projection
    pulls kind + value out of the nested `alternate_identifier` payload
    object (mirrors the events.py to_payload wire shape)."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetAlternateIdentifierAdded",
        {
            "asset_id": str(_ASSET_ID),
            "alternate_identifier": {"kind": "SerialNumber", "value": "SN-007"},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET alternate_identifiers" in sql
    # Dedupe (DISTINCT ON) + canonical sort (ORDER BY) are both in the
    # statement so a re-replay folds to a no-op at the DB layer.
    assert "DISTINCT ON" in sql
    assert "ORDER BY" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "SerialNumber"
    assert args.args[3] == "SN-007"


@pytest.mark.unit
async def test_alternate_identifier_removed_updates_jsonb_column() -> None:
    """The Removed event filters out the matching (kind, value) element
    from the alternate_identifiers JSONB array. The statement uses
    COALESCE so an array that collapses to empty stays `[]` (NOT NULL
    column)."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetAlternateIdentifierRemoved",
        {
            "asset_id": str(_ASSET_ID),
            "alternate_identifier": {"kind": "InventoryNumber", "value": "ANL-12345"},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "SET alternate_identifiers" in sql
    assert "COALESCE" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "InventoryNumber"
    assert args.args[3] == "ANL-12345"


@pytest.mark.unit
async def test_alternate_identifier_added_with_other_kind_passes_through() -> None:
    """`Other` is a valid third value in the AlternateIdentifierKind
    closed StrEnum (verbatim from PIDINST v1.0 Table 1). The projection
    is enum-agnostic: kind is just a string at this layer; the domain
    side guards the closed set."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetAlternateIdentifierAdded",
        {
            "asset_id": str(_ASSET_ID),
            "alternate_identifier": {"kind": "Other", "value": "operator-tag-2026-Q2"},
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "Other"
    assert args.args[3] == "operator-tag-2026-Q2"
