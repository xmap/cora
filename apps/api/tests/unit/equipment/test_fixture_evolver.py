"""Unit tests for the Fixture evolver: single-event genesis."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.fixture import (
    FixtureRegistered,
    SlotAssetBinding,
    evolve,
    fold,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_genesis_builds_state_from_event() -> None:
    fixture_id = uuid4()
    assembly_id = uuid4()
    asset_id = uuid4()
    surface_id = uuid4()
    bindings = frozenset({SlotAssetBinding(slot_name="camera", asset_id=asset_id)})
    event = FixtureRegistered(
        fixture_id=fixture_id,
        assembly_id=assembly_id,
        assembly_content_hash="a" * 64,
        surface_id=surface_id,
        slot_asset_bindings=bindings,
        parameter_overrides={"exposure_ms": 100},
        occurred_at=_NOW,
        registered_by=_TEST_ACTOR_ID,
    )
    state = evolve(None, event)
    assert state.id == fixture_id
    assert state.assembly_id == assembly_id
    assert state.assembly_content_hash == "a" * 64
    assert state.surface_id == surface_id
    assert state.slot_asset_bindings == bindings
    assert state.parameter_overrides == {"exposure_ms": 100}
    assert state.registered_at == _NOW


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_event_returns_state() -> None:
    event = FixtureRegistered(
        fixture_id=uuid4(),
        assembly_id=uuid4(),
        assembly_content_hash="x" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=frozenset(),
        parameter_overrides={},
        occurred_at=_NOW,
        registered_by=_TEST_ACTOR_ID,
    )
    state = fold([event])
    assert state is not None
    assert state.id == event.fixture_id
