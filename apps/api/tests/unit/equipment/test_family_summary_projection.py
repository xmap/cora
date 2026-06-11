"""Unit tests for FamilySummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Family events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import FamilySummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_CAPABILITY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Family",
        stream_id=_CAPABILITY_ID,
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
    proj = FamilySummaryProjection()
    assert proj.name == "proj_equipment_family_summary"

    assert proj.subscribed_event_types == frozenset(
        {
            "FamilyDefined",
            "FamilyVersioned",
            "FamilyDeprecated",
            "FamilySettingsSchemaUpdated",
            "FamilyPresentsAsAdded",
            "FamilyPresentsAsRemoved",
        }
    )


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_asset_events() -> None:
    """Asset events belong in the AssetSummaryProjection."""
    proj = FamilySummaryProjection()
    assert "AssetRegistered" not in proj.subscribed_event_types
    assert "AssetActivated" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_capability_defined_inserts_with_defined_status_and_null_version() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDefined",
        {
            "family_id": str(_CAPABILITY_ID),
            "name": "Continuous Rotation Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_family_summary" in sql
    assert "ON CONFLICT (family_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert "NULL" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "Continuous Rotation Tomography"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_family_defined_inserts_affordances_array() -> None:
    """FamilyDefined lands the declared affordance set on the
    projection so the AssetLookup PG adapter can JOIN and gate on it
    without folding the Family stream."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDefined",
        {
            "family_id": str(_CAPABILITY_ID),
            "name": "Tomography Detector",
            "occurred_at": _NOW.isoformat(),
            "affordances": ["Capturing", "Imageable"],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert "affordances" in args.args[0]
    assert args.args[4] == ["Capturing", "Imageable"]


@pytest.mark.unit
async def test_family_defined_missing_affordances_key_defaults_empty() -> None:
    """Legacy FamilyDefined payloads without the affordances key fold
    to an empty array (additive-state pattern)."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDefined",
        {
            "family_id": str(_CAPABILITY_ID),
            "name": "Legacy Family",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] == []


@pytest.mark.unit
async def test_family_versioned_replaces_affordances_array() -> None:
    """FamilyVersioned replaces the affordance set (the versioned set
    is the new declaration)."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyVersioned",
        {
            "family_id": str(_CAPABILITY_ID),
            "version_tag": "v2.0.0",
            "occurred_at": _NOW.isoformat(),
            "affordances": ["Capturing"],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert "affordances = $4" in args.args[0]
    assert args.args[4] == ["Capturing"]


@pytest.mark.unit
async def test_capability_versioned_updates_status_and_version_tag() -> None:
    """FamilyVersioned writes both status=Versioned AND the new
    version_tag from the payload (the only event that touches the
    version_tag column)."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyVersioned",
        {
            "family_id": str(_CAPABILITY_ID),
            "version_tag": "v2.1.0",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_family_summary" in sql
    assert "SET status = 'Versioned'" in sql
    assert "version_tag = $2" in sql
    assert "versioned_at = $3" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == "v2.1.0"
    assert args.args[3] == _NOW


@pytest.mark.unit
async def test_capability_deprecated_updates_status_and_preserves_version_tag() -> None:
    """FamilyDeprecated only touches `status`; `version_tag` is
    intentionally left alone so the audit trail of "what was the
    last revision before deprecation?" stays visible in the
    projection."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDeprecated",
        {
            "family_id": str(_CAPABILITY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_family_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "version_tag" not in sql
    assert "deprecated_at = $2" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == _NOW


# ---------- gate-review fill-ins (Path C) ----------


@pytest.mark.unit
async def test_family_versioned_replayed_overwrites_versioned_at() -> None:
    """Path C: re-version replaces versioned_at wholesale (state-always-
    holds-latest convention mirrored in projection). Mirrors the same
    treatment on Method."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    later = datetime(2026, 6, 1, 9, 30, 0, tzinfo=UTC)

    first = _stored(
        "FamilyVersioned",
        {
            "family_id": str(_CAPABILITY_ID),
            "version_tag": "v1.0.0",
            "occurred_at": _NOW.isoformat(),
        },
    )
    second = _stored(
        "FamilyVersioned",
        {
            "family_id": str(_CAPABILITY_ID),
            "version_tag": "v2.0.0",
            "occurred_at": later.isoformat(),
        },
    )

    await proj.apply(first, conn)
    await proj.apply(second, conn)

    assert conn.execute.await_count == 2
    second_args = conn.execute.await_args_list[1].args
    assert second_args[2] == "v2.0.0"
    assert second_args[3] == later


@pytest.mark.unit
async def test_family_lifecycle_timestamps_is_immutable_dataclass() -> None:
    """FamilyLifecycleTimestamps is the projection-sourced VO read by
    the route layer (Path C). Frozen so callers can't mutate it under
    cached references; field shape pinned so future widening shows up
    as a deliberate change."""
    import dataclasses

    from cora.equipment.aggregates.family import FamilyLifecycleTimestamps

    assert dataclasses.is_dataclass(FamilyLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(FamilyLifecycleTimestamps)}
    assert field_names == {"created_at", "versioned_at", "deprecated_at"}

    instance = FamilyLifecycleTimestamps(
        created_at=_NOW,
        versioned_at=None,
        deprecated_at=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.versioned_at = _NOW  # type: ignore[misc]


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_asset_registered_is_silently_dropped() -> None:
    """Cross-aggregate-event guard: AssetRegistered isn't in
    subscribed_event_types, but if the SQL filter ever lets one
    through, the bare match drops it without error."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored("AssetRegistered", {"asset_id": str(uuid4())})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


# ---- settings_schema_present folding -------------------------


_TEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
}


@pytest.mark.unit
async def test_capability_settings_schema_updated_with_schema_sets_present_true() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(_CAPABILITY_ID),
            "settings_schema": _TEST_SCHEMA,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_family_summary" in sql
    assert "settings_schema_present = $2" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] is True


@pytest.mark.unit
async def test_capability_settings_schema_updated_with_none_sets_present_false() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(_CAPABILITY_ID),
            "settings_schema": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_capability_settings_schema_updated_missing_payload_key_treated_as_none() -> None:
    """Tolerates payloads without the settings_schema key (treats as
    None / FALSE). Matches the from_stored additive-evolution
    stance."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilySettingsSchemaUpdated",
        {
            "family_id": str(_CAPABILITY_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] is False


@pytest.mark.unit
async def test_capability_defined_inserts_with_schema_present_false() -> None:
    """The genesis INSERT must default settings_schema_present to
    FALSE (no schema declared yet); pinned because the column
    default is FALSE in the migration AND the SQL literal is FALSE
    in _INSERT_CAPABILITY_SQL."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDefined",
        {
            "family_id": str(_CAPABILITY_ID),
            "name": "Tomography",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "FALSE" in sql  # explicit FALSE in INSERT


@pytest.mark.unit
async def test_family_defined_passes_affordances_payload_to_insert() -> None:
    """Affordances now ride the INSERT (Layer 3 3B added the column)."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyDefined",
        {
            "family_id": str(_CAPABILITY_ID),
            "name": "Camera",
            "occurred_at": _NOW.isoformat(),
            "affordances": ["Imageable", "Binnable"],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "ARRAY[]::UUID[]" in sql  # presents_as defaults empty
    assert args.args[4] == ["Imageable", "Binnable"]


@pytest.mark.unit
async def test_family_versioned_refreshes_affordances() -> None:
    """FamilyVersioned now writes the replacement affordance list."""
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "FamilyVersioned",
        {
            "family_id": str(_CAPABILITY_ID),
            "version_tag": "v2",
            "occurred_at": _NOW.isoformat(),
            "affordances": ["Streamable"],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "affordances = $4" in sql
    assert args.args[4] == ["Streamable"]


@pytest.mark.unit
async def test_family_presents_as_added_appends_distinct_role_id() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    role_id = uuid4()
    event = _stored(
        "FamilyPresentsAsAdded",
        {
            "family_id": str(_CAPABILITY_ID),
            "role_id": str(role_id),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "presents_as" in sql
    assert "DISTINCT" in sql  # idempotent append
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == role_id


@pytest.mark.unit
async def test_family_presents_as_removed_uses_array_remove() -> None:
    proj = FamilySummaryProjection()
    conn = AsyncMock()
    role_id = uuid4()
    event = _stored(
        "FamilyPresentsAsRemoved",
        {
            "family_id": str(_CAPABILITY_ID),
            "role_id": str(role_id),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "array_remove(presents_as, $2)" in sql
    assert args.args[1] == _CAPABILITY_ID
    assert args.args[2] == role_id
