"""Unit tests for the AssetPersistentIdAssigned evolver arm and the
carry-forward matrix that pins every non-persistent-id transition
preserves `persistent_id`."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
    AssetCondition,
    AssetDecommissioned,
    AssetDegraded,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetLifecycle,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetName,
    AssetOwner,
    AssetOwnerAdded,
    AssetOwnerName,
    AssetOwnerRemoved,
    AssetPersistentIdAssigned,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
    AssetTier,
    evolve,
    fold,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

pytestmark = pytest.mark.timeout(60, method="thread")

_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _extra_kwargs_for(transition: type) -> dict[str, object]:
    if transition is AssetDecommissioned:
        return {"decommissioned_by": _TEST_ACTOR_ID}
    return {}


_DOI = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.DOI,
    value="10.5281/zenodo.1234567",
)
_HANDLE = PersistentIdentifier(
    scheme=PersistentIdentifierScheme.HANDLE,
    value="20.500.12613/12345",
)


def _prior(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    persistent_id: PersistentIdentifier | None = None,
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        persistent_id=persistent_id,
    )


@pytest.mark.unit
def test_evolver_folds_asset_persistent_id_assigned_into_state() -> None:
    prior = _prior()
    assert prior.persistent_id is None
    state = evolve(
        prior,
        AssetPersistentIdAssigned(
            asset_id=prior.id,
            persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
            persistent_id_value="10.5281/zenodo.1234567",
            occurred_at=_NOW,
        ),
    )
    assert state.persistent_id == _DOI


@pytest.mark.unit
def test_evolver_folds_handle_scheme_correctly() -> None:
    prior = _prior()
    state = evolve(
        prior,
        AssetPersistentIdAssigned(
            asset_id=prior.id,
            persistent_id_scheme=PersistentIdentifierScheme.HANDLE.value,
            persistent_id_value="20.500.12613/12345",
            occurred_at=_NOW,
        ),
    )
    assert state.persistent_id == _HANDLE
    assert state.persistent_id is not None
    assert state.persistent_id.scheme is PersistentIdentifierScheme.HANDLE


@pytest.mark.unit
def test_evolver_preserves_unrelated_state_fields() -> None:
    """Persistent-id mutation only touches `persistent_id`; every other
    facet (lifecycle, condition, family_ids, settings, ports, drawing,
    model_id, alternate_identifiers, owners, fixture_id, parent_id,
    tier, name, id) carries through. Pin against the evolver
    explicitly constructing Asset(...) so a future evolver refactor
    that drops a field is caught."""
    asset_id = uuid4()
    parent_id = uuid4()
    fam = uuid4()
    fixture_id = uuid4()
    model_id = uuid4()
    owner = AssetOwner(name=AssetOwnerName("HZB"))
    alt_id = AlternateIdentifier(kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1")
    prior = Asset(
        id=asset_id,
        name=AssetName("Eiger-2X-9M"),
        tier=AssetTier.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.MAINTENANCE,
        condition=AssetCondition.DEGRADED,
        family_ids=frozenset({fam}),
        settings={"energy": 30, "filter": "Cu"},
        model_id=model_id,
        alternate_identifiers=frozenset({alt_id}),
        owners=frozenset({owner}),
        fixture_id=fixture_id,
    )
    state = evolve(
        prior,
        AssetPersistentIdAssigned(
            asset_id=asset_id,
            persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
            persistent_id_value="10.5281/zenodo.1234567",
            occurred_at=_NOW,
        ),
    )
    assert state.persistent_id == _DOI
    assert state.id == asset_id
    assert state.name == AssetName("Eiger-2X-9M")
    assert state.tier is AssetTier.DEVICE
    assert state.parent_id == parent_id
    assert state.lifecycle is AssetLifecycle.MAINTENANCE
    assert state.condition is AssetCondition.DEGRADED
    assert state.family_ids == frozenset({fam})
    assert state.settings == {"energy": 30, "filter": "Cu"}
    assert state.model_id == model_id
    assert state.alternate_identifiers == frozenset({alt_id})
    assert state.owners == frozenset({owner})
    assert state.fixture_id == fixture_id


@pytest.mark.unit
def test_evolver_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetPersistentIdAssigned(
                asset_id=uuid4(),
                persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
                persistent_id_value="10.5281/zenodo.1234567",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolver_replay_with_same_event_keeps_persistent_id_unchanged() -> None:
    """Set-once is enforced at the decider; the evolver itself is
    forgiving. A replay of the SAME AssetPersistentIdAssigned event
    yields the same `persistent_id`, so fold is idempotent at the
    evolver layer for the produced-by-decider stream."""
    prior = _prior()
    event = AssetPersistentIdAssigned(
        asset_id=prior.id,
        persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
        persistent_id_value="10.5281/zenodo.1234567",
        occurred_at=_NOW,
    )
    once = evolve(prior, event)
    twice = evolve(once, event)
    assert once.persistent_id == _DOI
    assert twice.persistent_id == _DOI


@pytest.mark.unit
def test_fold_register_then_assign_persistent_id_yields_asset_with_persistent_id() -> None:
    """End-to-end fold: register + assign yields an Asset whose
    `persistent_id` is the assigned VO."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetPersistentIdAssigned(
                asset_id=asset_id,
                persistent_id_scheme=PersistentIdentifierScheme.DOI.value,
                persistent_id_value="10.5281/zenodo.1234567",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.persistent_id == _DOI
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.unit
def test_evolver_asset_registered_defaults_persistent_id_to_none() -> None:
    """Genesis: AssetRegistered yields persistent_id=None via the state
    default (no synthetic initialization event). Pinned because legacy
    streams without persistent_id must fold cleanly via the
    additive-state pattern."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.persistent_id is None


_PRESERVATION_TRANSITIONS: list[tuple[str, type, dict[str, object]]] = [
    ("activate", AssetActivated, {}),
    ("decommission", AssetDecommissioned, {}),
    ("enter_maintenance", AssetMaintenanceEntered, {}),
    ("exit_maintenance", AssetMaintenanceExited, {}),
    ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
    ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
    ("degraded", AssetDegraded, {"reason": "x"}),
    ("faulted", AssetFaulted, {"reason": "x"}),
    ("restored", AssetRestored, {"reason": "x"}),
    ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    (
        "port_added",
        AssetPortAdded,
        {"port_name": "p1", "direction": "Input", "signal_type": "TTL"},
    ),
    ("port_removed", AssetPortRemoved, {"port_name": "p1"}),
    (
        "alt_id_added",
        AssetAlternateIdentifierAdded,
        {
            "alternate_identifier": AlternateIdentifier(
                kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1"
            ),
        },
    ),
    (
        "alt_id_removed",
        AssetAlternateIdentifierRemoved,
        {
            "alternate_identifier": AlternateIdentifier(
                kind=AlternateIdentifierKind.SERIAL_NUMBER, value="SN-1"
            ),
        },
    ),
    (
        "owner_added",
        AssetOwnerAdded,
        {"owner": AssetOwner(name=AssetOwnerName("ESRF"))},
    ),
    (
        "owner_removed",
        AssetOwnerRemoved,
        {"owner_name": AssetOwnerName("ESRF")},
    ),
]


def _pick_lifecycle_for(transition: type) -> AssetLifecycle:
    if transition is AssetActivated:
        return AssetLifecycle.COMMISSIONED
    if transition is AssetMaintenanceEntered:
        return AssetLifecycle.ACTIVE
    if transition is AssetMaintenanceExited:
        return AssetLifecycle.MAINTENANCE
    return AssetLifecycle.ACTIVE


@pytest.mark.unit
@pytest.mark.parametrize(("name", "transition", "kwargs"), _PRESERVATION_TRANSITIONS)
def test_evolve_non_persistent_id_transition_preserves_persistent_id(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Critical pin: every non-persistent-id Asset transition MUST
    carry `persistent_id` through from prior state. Constructing
    Asset(...) without explicitly passing `persistent_id` would
    silently wipe it to the None default. Same shape as the owners
    preservation pin."""
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=_pick_lifecycle_for(transition),
        persistent_id=_DOI,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.persistent_id == _DOI


@pytest.mark.unit
def test_evolve_relocate_preserves_persistent_id() -> None:
    """Hierarchy mutation also preserves persistent_id."""
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        persistent_id=_HANDLE,
    )
    state = evolve(
        prior,
        AssetRelocated(
            asset_id=prior.id,
            from_parent_id=old_parent,
            to_parent_id=new_parent,
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert state.persistent_id == _HANDLE
    assert state.parent_id == new_parent
