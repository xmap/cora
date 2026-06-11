"""Unit tests for the AssetOwner evolver arms and the carry-forward
matrix that pins every non-owner transition preserves `owners`."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
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
    AssetOwnerContact,
    AssetOwnerName,
    AssetOwnerRemoved,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
    AssetTier,
    evolve,
)
from cora.shared.identifier import (
    AlternateIdentifier,
    AlternateIdentifierKind,
)
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))
_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _extra_kwargs_for(transition: type) -> dict[str, object]:
    if transition is AssetDecommissioned:
        return {"decommissioned_by": _TEST_ACTOR_ID}
    return {}


_OWNER_A = AssetOwner(
    name=AssetOwnerName("HZB"),
    contact=AssetOwnerContact("ops@hzb.de"),
)
_OWNER_B = AssetOwner(name=AssetOwnerName("APS"))


def _prior(*, lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        owners=frozenset({_OWNER_A, _OWNER_B}),
    )


@pytest.mark.unit
def test_evolver_applies_asset_registered_with_owners_to_state() -> None:
    asset_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            owners=frozenset({_OWNER_A}),
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.owners == frozenset({_OWNER_A})


@pytest.mark.unit
def test_evolver_applies_asset_owner_added_appends_to_state() -> None:
    prior = _prior()
    new_owner = AssetOwner(name=AssetOwnerName("ESRF"))
    state = evolve(prior, AssetOwnerAdded(asset_id=prior.id, owner=new_owner, occurred_at=_NOW))
    assert state.owners == frozenset({_OWNER_A, _OWNER_B, new_owner})


@pytest.mark.unit
def test_evolver_applies_asset_owner_removed_removes_by_name_from_state() -> None:
    prior = _prior()
    state = evolve(
        prior,
        AssetOwnerRemoved(asset_id=prior.id, owner_name=_OWNER_A.name, occurred_at=_NOW),
    )
    assert state.owners == frozenset({_OWNER_B})


@pytest.mark.unit
def test_evolver_removing_last_owner_returns_to_empty() -> None:
    prior = _prior().__class__(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        owners=frozenset({_OWNER_A}),
    )
    state = evolve(
        prior,
        AssetOwnerRemoved(asset_id=prior.id, owner_name=_OWNER_A.name, occurred_at=_NOW),
    )
    assert state.owners == frozenset()


@pytest.mark.unit
def test_evolver_from_stored_malformed_owner_raises_value_error() -> None:
    """Malformed owner payloads on AssetRegistered surface as a wrapped
    ValueError per the from_stored convention with extra=(ValueError,)."""
    from cora.equipment.aggregates.asset.events import from_stored
    from cora.infrastructure.ports.event_store import StoredEvent

    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Asset",
        stream_id=uuid4(),
        version=1,
        event_type="AssetRegistered",
        schema_version=1,
        payload={
            "asset_id": str(uuid4()),
            "name": "X",
            "tier": "Unit",
            "parent_id": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
            "owners": [{"name": "   "}],  # whitespace -> InvalidAssetOwnerNameError
        },
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )
    with pytest.raises(ValueError, match="Malformed AssetRegistered"):
        from_stored(stored)


@pytest.mark.unit
def test_evolver_round_trip_preserves_owner_structural_equality() -> None:
    """to_payload + from_stored round-trips an AssetOwnerAdded event
    with the full VO populated."""
    from cora.equipment.aggregates.asset.events import (
        from_stored,
        to_payload,
    )
    from cora.infrastructure.ports.event_store import StoredEvent

    event = AssetOwnerAdded(
        asset_id=uuid4(),
        owner=AssetOwner(name=AssetOwnerName("HZB"), contact=AssetOwnerContact("ops@hzb.de")),
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    stored = StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Asset",
        stream_id=event.asset_id,
        version=1,
        event_type="AssetOwnerAdded",
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )
    rebuilt = from_stored(stored)
    assert rebuilt == event


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
def test_evolve_non_owner_transition_preserves_owners(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Critical pin per the design memo (Section 9.5 carry-forward
    coverage P1.10): every non-owner Asset transition MUST carry
    `owners` through from prior state. Constructing Asset(...) without
    explicitly passing `owners` would silently wipe it to the empty
    frozenset default."""
    _ = name
    prior = _prior(lifecycle=_pick_lifecycle_for(transition))
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.owners == frozenset({_OWNER_A, _OWNER_B})


@pytest.mark.unit
def test_evolve_relocate_preserves_owners() -> None:
    """Hierarchy mutation also preserves owners."""
    prior = _prior()
    new_parent = uuid4()
    state = evolve(
        prior,
        AssetRelocated(
            asset_id=prior.id,
            from_parent_id=prior.parent_id or uuid4(),
            to_parent_id=new_parent,
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert state.owners == frozenset({_OWNER_A, _OWNER_B})
