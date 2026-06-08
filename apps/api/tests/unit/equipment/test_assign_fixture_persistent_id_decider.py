"""Unit tests for the `assign_fixture_persistent_id` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureNotFoundError,
    FixturePersistentIdAlreadyAssignedError,
    FixturePersistentIdAssigned,
    SlotAssetBinding,
)
from cora.equipment.features import assign_fixture_persistent_id
from cora.equipment.features.assign_fixture_persistent_id.command import (
    AssignFixturePersistentId,
)
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _fixture(
    fixture_id: UUID,
    *,
    persistent_id: PersistentIdentifier | None = None,
    bound_asset_ids: frozenset[UUID] = frozenset(),
) -> Fixture:
    return Fixture(
        id=fixture_id,
        assembly_id=uuid4(),
        assembly_content_hash="a" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=frozenset(
            SlotAssetBinding(slot_name="camera", asset_id=aid) for aid in bound_asset_ids
        ),
        registered_at=_NOW,
        persistent_id=persistent_id,
    )


def _doi(value: str = "10.5281/zenodo.7654321") -> PersistentIdentifier:
    return PersistentIdentifier(scheme=PersistentIdentifierScheme.DOI, value=value)


def _cmd(fixture_id: UUID) -> AssignFixturePersistentId:
    return AssignFixturePersistentId(
        fixture_id=fixture_id,
        scheme=PersistentIdentifierScheme.DOI,
    )


def test_decider_with_state_none_raises_fixture_not_found_error() -> None:
    target_id = uuid4()
    identifier = _doi()
    with pytest.raises(FixtureNotFoundError) as exc_info:
        assign_fixture_persistent_id.decide(
            None,
            _cmd(target_id),
            persistent_id=identifier,
            now=_NOW,
        )
    assert exc_info.value.fixture_id == target_id


def test_decider_with_persistent_id_set_raises_fixture_persistent_id_already_assigned_error() -> (
    None
):
    existing = _doi("10.5281/zenodo.1111111")
    attempted = _doi("10.5281/zenodo.2222222")
    fixture_id = uuid4()
    state = _fixture(fixture_id, persistent_id=existing)
    with pytest.raises(FixturePersistentIdAlreadyAssignedError) as exc_info:
        assign_fixture_persistent_id.decide(
            state,
            _cmd(fixture_id),
            persistent_id=attempted,
            now=_NOW,
        )
    assert exc_info.value.fixture_id == fixture_id
    assert exc_info.value.current == existing
    assert exc_info.value.attempted == attempted


def test_decider_with_no_prior_assign_happy_path_emits_one_assigned_event() -> None:
    fixture_id = uuid4()
    state = _fixture(fixture_id)
    identifier = _doi()
    events = assign_fixture_persistent_id.decide(
        state,
        _cmd(fixture_id),
        persistent_id=identifier,
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], FixturePersistentIdAssigned)


def test_decider_emitted_event_carries_correct_fixture_id_scheme_value_now() -> None:
    fixture_id = uuid4()
    state = _fixture(fixture_id)
    identifier = _doi("10.5281/zenodo.9876543")
    events = assign_fixture_persistent_id.decide(
        state,
        _cmd(fixture_id),
        persistent_id=identifier,
        now=_NOW,
    )
    assert events == [
        FixturePersistentIdAssigned(
            fixture_id=fixture_id,
            persistent_id_scheme=identifier.scheme.value,
            persistent_id_value=identifier.value,
            occurred_at=_NOW,
        )
    ]
