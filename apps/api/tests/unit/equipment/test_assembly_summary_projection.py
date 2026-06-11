"""Unit tests for AssemblySummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the events
the projector subscribes to in v1 (AssemblyDefined only). Postgres-
side behavior lands in the integration suite when the slice for
define_assembly arrives.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections.assembly_summary import AssemblySummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ASSEMBLY_ID = uuid4()
_FAMILY_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Assembly",
        stream_id=_ASSEMBLY_ID,
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
    proj = AssemblySummaryProjection()
    assert proj.name == "proj_equipment_assembly_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "AssemblyDefined",
            "AssemblyVersioned",
            "AssemblyDeprecated",
            "AssemblyPresentsAsAdded",
            "AssemblyPresentsAsRemoved",
        }
    )


@pytest.mark.unit
async def test_assembly_defined_inserts_with_defined_status() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssemblyDefined",
        {
            "assembly_id": str(_ASSEMBLY_ID),
            "name": "MCTOptics",
            "presents_as_family_id": str(_FAMILY_ID),
            "required_slots": [],
            "required_wires": [],
            "parameter_overrides_schema": None,
            "drawing": None,
            "version": "v0.1.0",
            "content_hash": "a" * 64,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    # Positional args after the SQL string: assembly_id, name,
    # presents_as_family_id, version, content_hash, created_at.
    assert args.args[1] == _ASSEMBLY_ID
    assert args.args[2] == "MCTOptics"
    assert args.args[3] == _FAMILY_ID
    assert args.args[4] == "v0.1.0"
    assert args.args[5] == "a" * 64
    assert args.args[6] == _NOW


@pytest.mark.unit
async def test_assembly_defined_handles_null_version() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssemblyDefined",
        {
            "assembly_id": str(_ASSEMBLY_ID),
            "name": "MCTOptics",
            "presents_as_family_id": str(_FAMILY_ID),
            "required_slots": [],
            "required_wires": [],
            "parameter_overrides_schema": None,
            "drawing": None,
            "version": None,
            "content_hash": "b" * 64,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # version


@pytest.mark.unit
async def test_assembly_versioned_updates_status_name_family_version_hash() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    new_family_id = uuid4()
    event = _stored(
        "AssemblyVersioned",
        {
            "assembly_id": str(_ASSEMBLY_ID),
            "name": "MCTOptics-rev2",
            "presents_as_family_id": str(new_family_id),
            "required_slots": [],
            "required_wires": [],
            "parameter_overrides_schema": None,
            "drawing": None,
            "version": "v0.2.0",
            "content_hash": "c" * 64,
            "previous_content_hash": "a" * 64,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    # Positional args after the SQL: assembly_id, name,
    # presents_as_family_id, version, content_hash.
    assert args.args[1] == _ASSEMBLY_ID
    assert args.args[2] == "MCTOptics-rev2"
    assert args.args[3] == new_family_id
    assert args.args[4] == "v0.2.0"
    assert args.args[5] == "c" * 64


@pytest.mark.unit
async def test_assembly_deprecated_updates_status_to_deprecated() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssemblyDeprecated",
        {
            "assembly_id": str(_ASSEMBLY_ID),
            "reason": "superseded",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    # Single positional after the SQL: the assembly_id.
    assert args.args[1] == _ASSEMBLY_ID
    assert "Deprecated" in args.args[0]


@pytest.mark.unit
async def test_unrelated_event_type_is_silently_ignored() -> None:
    """Out-of-subscription events return without raising; the projector
    catalog is the source of truth for what gets folded."""
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {"assembly_id": str(_ASSEMBLY_ID)})
    await proj.apply(event, conn)
    assert conn.execute.await_count == 0


@pytest.mark.unit
async def test_assembly_defined_seeds_empty_presents_as() -> None:
    """Layer 3 3C: INSERT defaults presents_as to ARRAY[]::UUID[]."""
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssemblyDefined",
        {
            "assembly_id": str(_ASSEMBLY_ID),
            "name": "MCTOptics",
            "presents_as_family_id": str(_FAMILY_ID),
            "version": None,
            "content_hash": "abc",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "ARRAY[]::UUID[]" in sql


@pytest.mark.unit
async def test_assembly_presents_as_added_appends_distinct_role_id() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    role_id = uuid4()
    event = _stored(
        "AssemblyPresentsAsAdded",
        {
            "assembly_id": str(_ASSEMBLY_ID),
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
    assert "DISTINCT" in sql
    assert args.args[1] == _ASSEMBLY_ID
    assert args.args[2] == role_id


@pytest.mark.unit
async def test_assembly_presents_as_removed_uses_array_remove() -> None:
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    role_id = uuid4()
    event = _stored(
        "AssemblyPresentsAsRemoved",
        {
            "assembly_id": str(_ASSEMBLY_ID),
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
    assert args.args[1] == _ASSEMBLY_ID
    assert args.args[2] == role_id
