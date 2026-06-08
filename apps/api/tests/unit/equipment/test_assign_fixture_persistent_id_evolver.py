"""Unit tests for the FixturePersistentIdAssigned evolver arm.

Folding FixturePersistentIdAssigned over a Fixture state flips
`state.persistent_id` from None to PersistentIdentifier(scheme, value).
Replay-safe at the evolver layer; set-once is enforced at the decider.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.fixture import (
    Fixture,
    FixtureNotFoundError,
    FixturePersistentIdAssigned,
    FixtureRegistered,
    SlotAssetBinding,
    evolve,
    fold,
)
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 5, 12, 30, 0, tzinfo=UTC)

_DOI = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.DOI,
    value="10.5281/zenodo.7654321",
)
_HANDLE = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.HANDLE,
    value="20.500.12613/98765",
)


def _prior(
    *,
    persistent_id: PersistentIdentifier | None = None,
) -> Fixture:
    return Fixture(
        id=uuid4(),
        assembly_id=uuid4(),
        assembly_content_hash="b" * 64,
        surface_id=uuid4(),
        slot_asset_bindings=frozenset(),
        parameter_overrides={},
        registered_at=_NOW,
        persistent_id=persistent_id,
    )


@pytest.mark.unit
def test_evolver_folds_fixture_persistent_id_assigned_into_state() -> None:
    prior = _prior()
    assert prior.persistent_id is None
    state = evolve(
        prior,
        FixturePersistentIdAssigned(
            fixture_id=prior.id,
            persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
            persistent_id_value="10.5281/zenodo.7654321",
            occurred_at=_LATER,
        ),
    )
    assert state.persistent_id == _DOI


@pytest.mark.unit
def test_evolver_folds_handle_scheme_correctly() -> None:
    prior = _prior()
    state = evolve(
        prior,
        FixturePersistentIdAssigned(
            fixture_id=prior.id,
            persistent_id_scheme=PersistentIdentifierScheme.HANDLE.value,
            persistent_id_value="20.500.12613/98765",
            occurred_at=_LATER,
        ),
    )
    assert state.persistent_id == _HANDLE
    assert state.persistent_id is not None
    assert state.persistent_id.scheme is PersistentIdentifierScheme.HANDLE


@pytest.mark.unit
def test_evolver_preserves_unrelated_state_fields() -> None:
    """Persistent-id mutation only touches `persistent_id`; every other
    facet (id, assembly_id, assembly_content_hash, surface_id,
    slot_asset_bindings, parameter_overrides, registered_at) carries
    through. Pin against the evolver explicitly constructing
    Fixture(...) so a future evolver refactor that drops a field is
    caught."""
    fixture_id = uuid4()
    assembly_id = uuid4()
    surface_id = uuid4()
    asset_id = uuid4()
    bindings = frozenset({SlotAssetBinding(slot_name="camera", asset_id=asset_id)})
    prior = Fixture(
        id=fixture_id,
        assembly_id=assembly_id,
        assembly_content_hash="c" * 64,
        surface_id=surface_id,
        slot_asset_bindings=bindings,
        parameter_overrides={"exposure_ms": 100, "gain": "high"},
        registered_at=_NOW,
    )
    state = evolve(
        prior,
        FixturePersistentIdAssigned(
            fixture_id=fixture_id,
            persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
            persistent_id_value="10.5281/zenodo.7654321",
            occurred_at=_LATER,
        ),
    )
    assert state.persistent_id == _DOI
    assert state.id == fixture_id
    assert state.assembly_id == assembly_id
    assert state.assembly_content_hash == "c" * 64
    assert state.surface_id == surface_id
    assert state.slot_asset_bindings == bindings
    assert state.parameter_overrides == {"exposure_ms": 100, "gain": "high"}
    assert state.registered_at == _NOW


@pytest.mark.unit
def test_evolver_on_empty_state_raises_fixture_not_found() -> None:
    fixture_id = uuid4()
    with pytest.raises(FixtureNotFoundError):
        evolve(
            None,
            FixturePersistentIdAssigned(
                fixture_id=fixture_id,
                persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
                persistent_id_value="10.5281/zenodo.7654321",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolver_replay_with_same_event_keeps_persistent_id_unchanged() -> None:
    """Set-once is enforced at the decider; the evolver itself is
    forgiving. A replay of the SAME FixturePersistentIdAssigned event
    yields the same `persistent_id`, so fold is idempotent at the
    evolver layer for the produced-by-decider stream."""
    prior = _prior()
    event = FixturePersistentIdAssigned(
        fixture_id=prior.id,
        persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
        persistent_id_value="10.5281/zenodo.7654321",
        occurred_at=_LATER,
    )
    once = evolve(prior, event)
    twice = evolve(once, event)
    assert once.persistent_id == _DOI
    assert twice.persistent_id == _DOI


@pytest.mark.unit
def test_fold_register_then_assign_persistent_id_yields_fixture_with_persistent_id() -> None:
    """End-to-end fold: register + assign yields a Fixture whose
    `persistent_id` is the assigned VO and `registered_at` carries
    through from the genesis event."""
    fixture_id = uuid4()
    assembly_id = uuid4()
    surface_id = uuid4()
    state = fold(
        [
            FixtureRegistered(
                fixture_id=fixture_id,
                assembly_id=assembly_id,
                assembly_content_hash="d" * 64,
                surface_id=surface_id,
                slot_asset_bindings=frozenset(),
                parameter_overrides={},
                occurred_at=_NOW,
                registered_by=_TEST_ACTOR_ID,
            ),
            FixturePersistentIdAssigned(
                fixture_id=fixture_id,
                persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
                persistent_id_value="10.5281/zenodo.7654321",
                occurred_at=_LATER,
            ),
        ]
    )
    assert state is not None
    assert state.persistent_id == _DOI
    assert state.id == fixture_id
    assert state.registered_at == _NOW


@pytest.mark.unit
def test_evolver_fixture_registered_defaults_persistent_id_to_none() -> None:
    """Genesis: FixtureRegistered yields persistent_id=None via the
    state default (no synthetic initialization event). Pinned because
    legacy streams without persistent_id must fold cleanly via the
    additive-state pattern."""
    state = evolve(
        None,
        FixtureRegistered(
            fixture_id=uuid4(),
            assembly_id=uuid4(),
            assembly_content_hash="e" * 64,
            surface_id=uuid4(),
            slot_asset_bindings=frozenset(),
            parameter_overrides={},
            occurred_at=_NOW,
            registered_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.persistent_id is None


@pytest.mark.unit
def test_evolver_replay_assign_over_prior_persistent_id_overwrites_at_fold_layer() -> None:
    """The evolver is forgiving: if a stream somehow carries two
    FixturePersistentIdAssigned events (which the decider's set-once
    invariant forbids at command time), the evolver folds the second
    on top of the first without raising. Pin the forgiving posture so
    a future tightening at the evolver layer is a deliberate change."""
    prior = _prior(persistent_id=_DOI)
    state = evolve(
        prior,
        FixturePersistentIdAssigned(
            fixture_id=prior.id,
            persistent_id_scheme=PersistentIdentifierScheme.HANDLE.value,
            persistent_id_value="20.500.12613/98765",
            occurred_at=_LATER,
        ),
    )
    assert state.persistent_id == _HANDLE
