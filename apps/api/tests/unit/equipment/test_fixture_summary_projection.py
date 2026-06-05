"""Unit tests for FixtureSummaryProjection."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections.fixture_summary import FixtureSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_FIXTURE_ID = uuid4()
_ASSEMBLY_ID = uuid4()
_SURFACE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Fixture",
        stream_id=_FIXTURE_ID,
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
    proj = FixtureSummaryProjection()
    assert proj.name == "proj_equipment_fixture_summary"
    assert proj.subscribed_event_types == frozenset(
        {"FixtureRegistered", "FixturePersistentIdAssigned"}
    )


@pytest.mark.unit
async def test_fixture_registered_inserts_summary_counts() -> None:
    proj = FixtureSummaryProjection()
    conn = AsyncMock()
    asset_a = uuid4()
    asset_b = uuid4()
    event = _stored(
        "FixtureRegistered",
        {
            "fixture_id": str(_FIXTURE_ID),
            "assembly_id": str(_ASSEMBLY_ID),
            "assembly_content_hash": "a" * 64,
            "surface_id": str(_SURFACE_ID),
            "slot_asset_bindings": [
                {"slot_name": "camera", "asset_id": str(asset_a)},
                {"slot_name": "rotary", "asset_id": str(asset_b)},
            ],
            "parameter_overrides": {"exposure_ms": 100},
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    # Positional args after SQL: fixture_id, assembly_id,
    # assembly_content_hash, surface_id, binding_count, override_count,
    # created_at.
    assert args.args[1] == _FIXTURE_ID
    assert args.args[2] == _ASSEMBLY_ID
    assert args.args[3] == "a" * 64
    assert args.args[4] == _SURFACE_ID
    assert args.args[5] == 2  # binding_count
    assert args.args[6] == 1  # override_count
    assert args.args[7] == _NOW


@pytest.mark.unit
async def test_unrelated_event_type_is_silently_ignored() -> None:
    proj = FixtureSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {"fixture_id": str(_FIXTURE_ID)})
    await proj.apply(event, conn)
    assert conn.execute.await_count == 0
