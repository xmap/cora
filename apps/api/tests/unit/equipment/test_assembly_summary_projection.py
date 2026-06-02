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
    assert proj.subscribed_event_types == frozenset({"AssemblyDefined"})


@pytest.mark.unit
def test_projection_does_not_subscribe_to_versioned_or_deprecated_in_v1() -> None:
    """v1 ships AssemblyDefined arm only; the Versioned and Deprecated
    arms land with their respective slices per the slice-per-commit
    discipline."""
    proj = AssemblySummaryProjection()
    assert "AssemblyVersioned" not in proj.subscribed_event_types
    assert "AssemblyDeprecated" not in proj.subscribed_event_types


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
async def test_unrelated_event_type_is_silently_ignored() -> None:
    """Out-of-subscription events return without raising; the projector
    catalog is the source of truth for what gets folded."""
    proj = AssemblySummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {"assembly_id": str(_ASSEMBLY_ID)})
    await proj.apply(event, conn)
    assert conn.execute.await_count == 0
