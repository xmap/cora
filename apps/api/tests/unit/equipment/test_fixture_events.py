"""Unit tests for Fixture events: round-trip + canonicalization."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.fixture import (
    FixtureRegistered,
    SlotAssetBinding,
    from_stored,
    to_payload,
)
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))


_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Fixture",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_fixture_registered_to_payload_then_from_stored_round_trip() -> None:
    bindings = frozenset(
        {
            SlotAssetBinding(slot_name="camera", asset_id=uuid4()),
            SlotAssetBinding(slot_name="rotary", asset_id=uuid4()),
        }
    )
    original = FixtureRegistered(
        fixture_id=uuid4(),
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=bindings,
        parameter_overrides={"exposure_ms": 250},
        occurred_at=_NOW,
        registered_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(original)
    rebuilt = from_stored(_stored("FixtureRegistered", payload))
    assert rebuilt == original


@pytest.mark.unit
def test_fixture_registered_payload_serializes_bindings_as_sorted_list() -> None:
    """Canonical ordering: bindings serialize as a sorted list of dicts."""
    bindings = frozenset(
        {
            SlotAssetBinding(slot_name="z_motor", asset_id=uuid4()),
            SlotAssetBinding(slot_name="a_camera", asset_id=uuid4()),
        }
    )
    event = FixtureRegistered(
        fixture_id=uuid4(),
        assembly_id=uuid4(),
        assembly_content_hash="x" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=bindings,
        parameter_overrides={},
        occurred_at=_NOW,
        registered_by=_TEST_ACTOR_ID,
    )
    payload = to_payload(event)
    bindings_payload = cast("list[dict[str, str]]", payload["slot_asset_bindings"])
    assert isinstance(bindings_payload, list)
    slot_names = [entry["slot_name"] for entry in bindings_payload]
    assert slot_names == sorted(slot_names)


@pytest.mark.unit
def test_unknown_event_type_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown FixtureEvent event_type"):
        from_stored(_stored("UnknownEvent", {}))
