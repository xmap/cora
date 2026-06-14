"""Unit tests for the Asset aggregate's evolver."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetLifecycle,
    AssetName,
    AssetTier,
    evolve,
    fold,
)
from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetAlternateIdentifierAdded,
    AssetAlternateIdentifierRemoved,
    AssetAttachedToFixture,
    AssetDecommissioned,
    AssetDegraded,
    AssetFamilyAdded,
    AssetFamilyRemoved,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetMaintenanceExited,
    AssetOwnerRemoved,
    AssetPortAdded,
    AssetPortRemoved,
    AssetRegistered,
    AssetRelocated,
    AssetRestored,
    AssetSettingsUpdated,
)
from cora.equipment.aggregates.asset.state import (
    AlternateIdentifier,
    AlternateIdentifierKind,
    AssetOwner,
    AssetOwnerName,
    AssetPort,
    PortDirection,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))
_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _facility_result(code: str = "cora") -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


def _extra_kwargs_for(transition: type) -> dict[str, object]:
    """Inject required fold-symmetry attribution kwargs for transitions
    that carry them. Returns {} for transitions without attribution."""
    if transition is AssetDecommissioned:
        return {"decommissioned_by": _TEST_ACTOR_ID}
    return {}


@pytest.mark.unit
def test_evolve_asset_registered_sets_lifecycle_to_commissioned() -> None:
    """AssetRegistered is the genesis event; lifecycle defaults to
    Commissioned via the evolver. Pin so a future change (for example adding
    `initial_lifecycle` to the event payload) is a deliberate
    additive-state evolution."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="APS-2BM",
            tier="Unit",
            parent_id=parent_id,
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_evolve_asset_registered_handles_unit_with_null_parent() -> None:
    """The other genesis case: a root (Unit-tier) Asset has parent_id=None."""
    asset_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="ANL",
            tier="Unit",
            parent_id=None,
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("ANL"),
        tier=AssetTier.UNIT,
        parent_id=None,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_evolve_reconstructs_tier_from_payload_string() -> None:
    """`tier` is carried in the payload as a string and reconstructed
    via `AssetTier(tier)`. Pin that the round-trip works for every
    tier (otherwise an AssetTier addition would silently break
    persisted streams)."""
    for tier in AssetTier:
        state = evolve(
            None,
            AssetRegistered(
                asset_id=uuid4(),
                name="Anything",
                tier=tier.value,
                parent_id=uuid4(),
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
        )
        assert state.tier is tier


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_asset_registered_returns_asset() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="Eiger-2X-9M",
                tier="Device",
                parent_id=parent_id,
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            )
        ]
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("Eiger-2X-9M"),
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
        tier=AssetTier.DEVICE,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    events = [
        AssetRegistered(
            asset_id=asset_id,
            name="APS-2BM",
            tier="Unit",
            parent_id=parent_id,
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip_for_root() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state. Root case (the null-parent case binds a
    facility_code)."""
    new_id = uuid4()
    command = RegisterAsset(
        name="  ANL  ", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
    )
    events = register_asset.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=_facility_result("cora"),
    )
    rebuilt = fold(events)
    assert rebuilt == Asset(
        id=new_id,
        name=AssetName("ANL"),
        tier=AssetTier.UNIT,
        parent_id=None,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
        facility_code=FacilityCode("cora"),
    )


@pytest.mark.unit
def test_decider_and_evolver_round_trip_for_device_with_parent() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state. Device-level (the typical with-parent case)."""
    new_id = uuid4()
    parent_id = uuid4()
    command = RegisterAsset(name="Eiger-2X-9M", tier=AssetTier.DEVICE, parent_id=parent_id)
    events = register_asset.decide(
        state=None,
        command=command,
        now=_NOW,
        new_id=new_id,
        commissioned_by=_TEST_ACTOR_ID,
        facility_lookup_result=None,
    )
    rebuilt = fold(events)
    assert rebuilt == Asset(
        id=new_id,
        name=AssetName("Eiger-2X-9M"),
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
        commissioned_at=_NOW,
        commissioned_by=_TEST_ACTOR_ID,
        tier=AssetTier.DEVICE,
    )


# ---------- AssetActivated ----------


@pytest.mark.unit
def test_evolve_asset_activated_flips_lifecycle_to_active() -> None:
    """AssetActivated folded onto a Commissioned asset sets
    lifecycle=ACTIVE. Lifecycle field is NOT in the event payload;
    the evolver derives it from the event TYPE (same precedent as
    SubjectMounted)."""
    asset_id = uuid4()
    parent_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    activated = evolve(commissioned, AssetActivated(asset_id=asset_id, occurred_at=_NOW))
    assert activated == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )


@pytest.mark.unit
def test_evolve_asset_activated_preserves_id_name_level_parent() -> None:
    """The evolver only updates `lifecycle`; id/name/level/parent_id
    are carried over from prior state. Pinned because Asset has more
    state fields than the simpler aggregates — a refactor that built
    Asset from event fields only would silently drop them."""
    asset_id = uuid4()
    parent_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("Original"),
        tier=AssetTier.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    activated = evolve(commissioned, AssetActivated(asset_id=asset_id, occurred_at=_NOW))
    assert activated.id == asset_id
    assert activated.name == AssetName("Original")
    assert activated.tier is AssetTier.DEVICE
    assert activated.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_activated_on_empty_state_raises() -> None:
    """AssetActivated before AssetRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetActivated(asset_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_then_activate_yields_active_asset() -> None:
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
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.ACTIVE


# ---------- AssetDecommissioned ----------


@pytest.mark.unit
def test_evolve_asset_decommissioned_from_commissioned_flips_to_decommissioned() -> None:
    """Multi-source: Commissioned -> Decommissioned (operator changed
    mind, decommissioning before activation)."""
    asset_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    decommed = evolve(
        commissioned,
        AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID),
    )
    assert decommed.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_evolve_asset_decommissioned_from_active_flips_to_decommissioned() -> None:
    """Multi-source: Active -> Decommissioned (typical retirement
    path). Pinned so a future change that only handles one source
    state in the evolver is caught."""
    asset_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
    )
    decommed = evolve(
        active,
        AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID),
    )
    assert decommed.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_evolve_asset_decommissioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetDecommissioned(
                asset_id=uuid4(), occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        )


@pytest.mark.unit
def test_fold_register_activate_decommission_yields_decommissioned_asset() -> None:
    """End-to-end fold: register + activate + decommission produces
    a Decommissioned asset (the typical lifecycle path)."""
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
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_fold_register_decommission_yields_decommissioned_asset() -> None:
    """End-to-end fold: register + decommission (skipping activate)
    produces a Decommissioned asset. Pinned because the multi-source
    contract has to be honored at the fold level too, not just the
    decider."""
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
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


# ---------- AssetRelocated ----------


@pytest.mark.unit
def test_evolve_asset_relocated_mutates_parent_id_to_target() -> None:
    """The evolver reads `to_parent_id` (target) and writes it to
    state.parent_id. `from_parent_id` is audit metadata only — not
    read by the evolver. Pinned to lock the source-of-truth contract."""
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    relocated = evolve(
        commissioned,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=old_parent,
            to_parent_id=new_parent,
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.parent_id == new_parent


@pytest.mark.unit
def test_evolve_asset_relocated_preserves_lifecycle() -> None:
    """Hierarchy mutation is NOT a state transition — lifecycle is
    carried over from prior state. Pinned because adding a "lifecycle"
    side-effect to relocate would silently change Asset behavior."""
    asset_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
    )
    relocated = evolve(
        active,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=active.parent_id or uuid4(),
            to_parent_id=uuid4(),
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
def test_evolve_asset_relocated_preserves_id_name_level() -> None:
    """Only parent_id changes. Pinned: the relocate arm has more
    fields to carry than the simple lifecycle transitions."""
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("Original"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    relocated = evolve(
        prior,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=prior.parent_id or uuid4(),
            to_parent_id=uuid4(),
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.id == asset_id
    assert relocated.name == AssetName("Original")
    assert relocated.tier is AssetTier.DEVICE


@pytest.mark.unit
def test_evolve_asset_relocated_on_empty_state_raises() -> None:
    """Relocate before Register = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetRelocated(
                asset_id=uuid4(),
                from_parent_id=uuid4(),
                to_parent_id=uuid4(),
                reason="moved",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_fold_register_then_relocate_yields_asset_with_new_parent() -> None:
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=old_parent,
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetRelocated(
                asset_id=asset_id,
                from_parent_id=old_parent,
                to_parent_id=new_parent,
                reason="site reorganization",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.parent_id == new_parent
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.unit
def test_fold_register_activate_relocate_preserves_active_lifecycle() -> None:
    """Relocate after activate keeps lifecycle=ACTIVE — the typical
    in-service hierarchy move case."""
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=old_parent,
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetRelocated(
                asset_id=asset_id,
                from_parent_id=old_parent,
                to_parent_id=new_parent,
                reason="moved while in service",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.parent_id == new_parent
    assert state.lifecycle is AssetLifecycle.ACTIVE


# ---------- AssetMaintenanceEntered ----------


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_flips_lifecycle_to_maintenance() -> None:
    """AssetMaintenanceEntered folded onto an Active asset sets
    lifecycle=MAINTENANCE. Lifecycle field is NOT in the event
    payload; the evolver derives it from the event TYPE (same
    convention as AssetActivated)."""
    asset_id = uuid4()
    parent_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )
    in_maintenance = evolve(active, AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW))
    assert in_maintenance == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.MAINTENANCE,
    )


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_preserves_id_name_level_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("Original"),
        tier=AssetTier.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )
    in_maintenance = evolve(active, AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW))
    assert in_maintenance.id == asset_id
    assert in_maintenance.name == AssetName("Original")
    assert in_maintenance.tier is AssetTier.DEVICE
    assert in_maintenance.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW))


# ---------- AssetMaintenanceExited ----------


@pytest.mark.unit
def test_evolve_asset_maintenance_exited_flips_lifecycle_to_active() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    in_maintenance = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.MAINTENANCE,
    )
    exited = evolve(
        in_maintenance,
        AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
    )
    assert exited.lifecycle is AssetLifecycle.ACTIVE
    assert exited.id == asset_id
    assert exited.name == AssetName("APS-2BM")
    assert exited.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_maintenance_exited_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetMaintenanceExited(asset_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_activate_enter_asset_maintenance_yields_maintenance_asset() -> None:
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
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.MAINTENANCE


@pytest.mark.unit
def test_fold_register_activate_enter_exit_yields_active_asset() -> None:
    """Full maintenance round-trip: enter then exit returns to Active."""
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
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
def test_fold_register_activate_enter_decommission_yields_decommissioned_asset() -> None:
    """Maintenance is the third allowed source for decommission (5e
    widening). Pinned at fold level so the multi-source contract
    holds end-to-end."""
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
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


# ---------- AssetFamilyAdded / Removed ----------


@pytest.mark.unit
def test_evolve_asset_registered_starts_with_empty_capabilities() -> None:
    """Genesis-only stream folds to empty frozenset (additive-state
    pattern: streams without the new field fold cleanly without an upcaster)."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="APS-2BM",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.family_ids == frozenset()


@pytest.mark.unit
def test_evolve_asset_capability_added_inserts_into_capabilities() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    cap1 = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        tier=AssetTier.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
        family_ids=frozenset(),
    )
    state = evolve(
        prior,
        AssetFamilyAdded(asset_id=asset_id, family_id=cap1, occurred_at=_NOW),
    )
    assert state.family_ids == frozenset({cap1})
    # Other state preserved.
    assert state.lifecycle is AssetLifecycle.ACTIVE
    assert state.parent_id == parent_id
    assert state.id == asset_id


@pytest.mark.unit
def test_evolve_asset_capability_added_is_idempotent_at_evolver_layer() -> None:
    """Evolver does NOT enforce strict-not-idempotent; that's the
    decider's job. Frozenset semantics: adding an already-present id
    is a no-op at this layer. Pinned because a future evolver that
    raised on duplicate would couple the evolver to command-time
    semantics, which it shouldn't."""
    cap1 = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        family_ids=frozenset({cap1}),
    )
    state = evolve(
        prior,
        AssetFamilyAdded(asset_id=prior.id, family_id=cap1, occurred_at=_NOW),
    )
    assert state.family_ids == frozenset({cap1})


@pytest.mark.unit
def test_evolve_asset_capability_removed_drops_from_capabilities() -> None:
    cap1 = uuid4()
    cap2 = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        family_ids=frozenset({cap1, cap2}),
    )
    state = evolve(
        prior,
        AssetFamilyRemoved(asset_id=prior.id, family_id=cap1, occurred_at=_NOW),
    )
    assert state.family_ids == frozenset({cap2})


@pytest.mark.unit
def test_evolve_asset_capability_removed_is_idempotent_at_evolver_layer() -> None:
    """Same rationale as Added's idempotent-at-evolver pin."""
    cap1 = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        family_ids=frozenset(),
    )
    state = evolve(
        prior,
        AssetFamilyRemoved(asset_id=prior.id, family_id=cap1, occurred_at=_NOW),
    )
    assert state.family_ids == frozenset()


@pytest.mark.unit
def test_evolve_asset_capability_added_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetFamilyAdded(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW),
        )


@pytest.mark.unit
def test_evolve_asset_capability_removed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetFamilyRemoved(asset_id=uuid4(), family_id=uuid4(), occurred_at=_NOW),
        )


# ---------- Family preservation across transition arms ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_asset_maintenance", AssetMaintenanceEntered),
        ("exit_asset_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_capabilities(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every transition arm MUST carry capabilities
    through from prior state. Constructing Asset(...) without
    explicitly passing capabilities would silently WIPE the field to
    its default (empty frozenset). 5f-1 added the field with a
    default solely for forward-compat on AssetRegistered events; all
    transition arms must explicitly carry it. This parametrize is the
    safety net."""
    _ = name  # parametrize id only
    cap1 = uuid4()
    cap2 = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        # Set lifecycle so each transition has a valid source state at
        # the FOLD layer (decider-time guards live elsewhere).
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE  # decommission accepts any of 3
        ),
        family_ids=frozenset({cap1, cap2}),
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition)),
    )
    assert state.family_ids == frozenset({cap1, cap2})


@pytest.mark.unit
def test_evolve_relocate_preserves_capabilities() -> None:
    """Hierarchy mutation also must preserve capabilities."""
    cap1 = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        family_ids=frozenset({cap1}),
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
    assert state.family_ids == frozenset({cap1})
    assert state.parent_id == new_parent


@pytest.mark.unit
def test_fold_register_add_remove_yields_empty_capabilities() -> None:
    """End-to-end audit: capability added then removed leaves the
    asset back at empty. Pin so the round-trip pair holds at the fold
    level too."""
    asset_id = uuid4()
    cap1 = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=uuid4(),
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetFamilyAdded(asset_id=asset_id, family_id=cap1, occurred_at=_NOW),
            AssetFamilyRemoved(asset_id=asset_id, family_id=cap1, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.family_ids == frozenset()


# ---------- condition transitions + preservation ----------


@pytest.mark.unit
def test_evolve_asset_registered_defaults_condition_to_nominal() -> None:
    """Genesis: AssetRegistered yields condition=Nominal via the
    state default (no synthetic initialization event)."""
    asset_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.condition is AssetCondition.NOMINAL


@pytest.mark.unit
def test_evolve_asset_degraded_sets_condition_to_degraded() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    state = evolve(prior, AssetDegraded(asset_id=asset_id, reason="hot pixel", occurred_at=_NOW))
    assert state.condition is AssetCondition.DEGRADED


@pytest.mark.unit
def test_evolve_asset_faulted_sets_condition_to_faulted() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    state = evolve(prior, AssetFaulted(asset_id=asset_id, reason="seized", occurred_at=_NOW))
    assert state.condition is AssetCondition.FAULTED


@pytest.mark.unit
def test_evolve_asset_restored_sets_condition_to_nominal() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        condition=AssetCondition.FAULTED,
    )
    state = evolve(prior, AssetRestored(asset_id=asset_id, reason="repaired", occurred_at=_NOW))
    assert state.condition is AssetCondition.NOMINAL


@pytest.mark.unit
def test_evolve_condition_transition_preserves_lifecycle_and_capabilities() -> None:
    """Condition transitions don't touch lifecycle / capabilities /
    parent_id / level / name. Pin so a future evolver mistake doesn't
    silently couple the dimensions."""
    asset_id = uuid4()
    parent = uuid4()
    cap = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=parent,
        lifecycle=AssetLifecycle.MAINTENANCE,
        condition=AssetCondition.NOMINAL,
        family_ids=frozenset({cap}),
    )
    state = evolve(prior, AssetFaulted(asset_id=asset_id, reason="test", occurred_at=_NOW))
    assert state.lifecycle is AssetLifecycle.MAINTENANCE
    assert state.family_ids == frozenset({cap})
    assert state.parent_id == parent
    assert state.tier is AssetTier.DEVICE
    assert state.name == AssetName("X")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_asset_maintenance", AssetMaintenanceEntered),
        ("exit_asset_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_condition(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    condition through from prior state. Constructing Asset(...)
    without explicitly passing condition would silently WIPE it to
    NOMINAL. Same shape as the capabilities-preservation pin."""
    _ = name  # parametrize id only
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        condition=AssetCondition.FAULTED,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition)),
    )
    assert state.condition is AssetCondition.FAULTED


@pytest.mark.unit
def test_evolve_relocate_preserves_condition() -> None:
    """Hierarchy mutation also must preserve condition."""
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        condition=AssetCondition.DEGRADED,
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
    assert state.condition is AssetCondition.DEGRADED


@pytest.mark.unit
def test_evolve_capability_added_preserves_condition() -> None:
    cap = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        condition=AssetCondition.DEGRADED,
    )
    state = evolve(
        prior,
        AssetFamilyAdded(asset_id=prior.id, family_id=cap, occurred_at=_NOW),
    )
    assert state.condition is AssetCondition.DEGRADED


@pytest.mark.unit
def test_evolve_capability_removed_preserves_condition() -> None:
    cap = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        condition=AssetCondition.DEGRADED,
        family_ids=frozenset({cap}),
    )
    state = evolve(
        prior,
        AssetFamilyRemoved(asset_id=prior.id, family_id=cap, occurred_at=_NOW),
    )
    assert state.condition is AssetCondition.DEGRADED


@pytest.mark.unit
def test_fold_register_then_fault_then_restore_round_trip() -> None:
    """End-to-end audit: register -> fault -> restore lands at
    Nominal. Pin so the fold layer faithfully reflects the
    target-state semantics across the three condition events."""
    asset_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="X",
                tier="Unit",
                parent_id=uuid4(),
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetFaulted(asset_id=asset_id, reason="bad", occurred_at=_NOW),
            AssetRestored(asset_id=asset_id, reason="fixed", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.condition is AssetCondition.NOMINAL


# ---------- settings transitions + preservation ----------


@pytest.mark.unit
def test_evolve_asset_registered_defaults_settings_to_empty_dict() -> None:
    """Genesis: AssetRegistered yields settings={} via the state
    default (no synthetic initialization event)."""
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
    assert state.settings == {}


@pytest.mark.unit
def test_evolve_asset_settings_updated_replaces_settings() -> None:
    """The event payload carries the FULL post-merge dict (5g-c
    lock), so the evolver simply replaces."""
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        settings={"old_key": "old_value"},
    )
    state = evolve(
        prior,
        AssetSettingsUpdated(
            asset_id=asset_id,
            settings={"new_key_a": 1, "new_key_b": "hello"},
            occurred_at=_NOW,
        ),
    )
    assert state.settings == {"new_key_a": 1, "new_key_b": "hello"}
    # Old key fully gone — settings is REPLACED, not merged at the
    # evolver layer (merging happens in the decider).
    assert "old_key" not in state.settings


@pytest.mark.unit
def test_evolve_settings_transition_preserves_lifecycle_condition_capabilities() -> None:
    """Settings transitions don't touch other facets. Pin orthogonality."""
    asset_id = uuid4()
    cap = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.MAINTENANCE,
        condition=AssetCondition.DEGRADED,
        family_ids=frozenset({cap}),
        settings={"a": 1},
    )
    state = evolve(
        prior,
        AssetSettingsUpdated(asset_id=asset_id, settings={"b": 2}, occurred_at=_NOW),
    )
    assert state.lifecycle is AssetLifecycle.MAINTENANCE
    assert state.condition is AssetCondition.DEGRADED
    assert state.family_ids == frozenset({cap})
    assert state.settings == {"b": 2}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_asset_maintenance", AssetMaintenanceEntered),
        ("exit_asset_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_settings(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    settings through. Same shape as condition / capabilities
    preservation."""
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        settings={"energy": 30, "filter": "Cu"},
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.settings == {"energy": 30, "filter": "Cu"}


@pytest.mark.unit
def test_evolve_relocate_preserves_settings() -> None:
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        settings={"a": 1},
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
    assert state.settings == {"a": 1}


@pytest.mark.unit
def test_evolve_capability_added_preserves_settings() -> None:
    cap = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        settings={"a": 1},
    )
    state = evolve(
        prior,
        AssetFamilyAdded(asset_id=prior.id, family_id=cap, occurred_at=_NOW),
    )
    assert state.settings == {"a": 1}


@pytest.mark.unit
def test_evolve_capability_removed_preserves_settings_orphans() -> None:
    """5g-c lock: settings keys provided by a removed Family
    STAY on the Asset (no auto-purge). Pin against the evolver."""
    cap = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        family_ids=frozenset({cap}),
        settings={"key_owned_by_removed_cap": "value"},
    )
    state = evolve(
        prior,
        AssetFamilyRemoved(asset_id=prior.id, family_id=cap, occurred_at=_NOW),
    )
    assert state.family_ids == frozenset()
    # Orphan key is preserved.
    assert state.settings == {"key_owned_by_removed_cap": "value"}


@pytest.mark.unit
def test_evolve_condition_event_preserves_settings() -> None:
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        settings={"a": 1},
    )
    state = evolve(prior, AssetFaulted(asset_id=prior.id, reason="x", occurred_at=_NOW))
    assert state.settings == {"a": 1}


# ---------- ports transitions + preservation ----------


@pytest.mark.unit
def test_evolve_asset_registered_defaults_ports_to_empty_frozenset() -> None:
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
    assert state.ports == frozenset()


@pytest.mark.unit
def test_evolve_asset_port_added_inserts_port_into_frozenset() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=asset_id,
            port_name="trigger_in",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert (
        AssetPort(name="trigger_in", direction=PortDirection.INPUT, signal_type="TTL")
        in state.ports
    )


@pytest.mark.unit
def test_evolve_asset_port_removed_removes_by_name_only() -> None:
    """The removed port may have any direction/signal_type; the
    evolver matches by name alone (the unique key)."""
    asset_id = uuid4()
    keep = AssetPort(name="keep", direction=PortDirection.INPUT, signal_type="TTL")
    drop = AssetPort(name="drop", direction=PortDirection.OUTPUT, signal_type="LVDS")
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        ports=frozenset({keep, drop}),
    )
    state = evolve(
        prior,
        AssetPortRemoved(asset_id=asset_id, port_name="drop", occurred_at=_NOW),
    )
    assert state.ports == frozenset({keep})


@pytest.mark.unit
def test_evolve_lifecycle_transition_preserves_ports() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
        ports=frozenset({port}),
    )
    state = evolve(prior, AssetActivated(asset_id=prior.id, occurred_at=_NOW))
    assert state.ports == frozenset({port})


@pytest.mark.unit
def test_evolve_settings_transition_preserves_ports() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        ports=frozenset({port}),
    )
    state = evolve(
        prior,
        AssetSettingsUpdated(asset_id=prior.id, settings={"a": 1}, occurred_at=_NOW),
    )
    assert state.ports == frozenset({port})


@pytest.mark.unit
def test_evolve_port_added_preserves_other_facets() -> None:
    """Port mutations must not touch lifecycle / condition / settings /
    capabilities / parent_id."""
    asset_id = uuid4()
    parent = uuid4()
    cap = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=parent,
        lifecycle=AssetLifecycle.MAINTENANCE,
        condition=AssetCondition.DEGRADED,
        family_ids=frozenset({cap}),
        settings={"k": 1},
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=asset_id,
            port_name="x",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert state.lifecycle is AssetLifecycle.MAINTENANCE
    assert state.condition is AssetCondition.DEGRADED
    assert state.family_ids == frozenset({cap})
    assert state.settings == {"k": 1}
    assert state.parent_id == parent


@pytest.mark.unit
def test_fold_register_then_add_then_remove_yields_empty_ports() -> None:
    """End-to-end: register -> add port -> remove port lands at
    empty ports. Pin against the fold layer."""
    asset_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="X",
                tier="Unit",
                parent_id=uuid4(),
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetPortAdded(
                asset_id=asset_id,
                port_name="trigger_in",
                direction="Input",
                signal_type="TTL",
                occurred_at=_NOW,
            ),
            AssetPortRemoved(asset_id=asset_id, port_name="trigger_in", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.ports == frozenset()


_SAMPLE_DRAWING = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")


@pytest.mark.unit
def test_evolve_register_with_drawing_carries_drawing_into_state() -> None:
    asset_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            drawing=_SAMPLE_DRAWING,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.drawing == _SAMPLE_DRAWING


@pytest.mark.unit
def test_evolve_register_without_drawing_yields_none() -> None:
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
    assert state.drawing is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_asset_maintenance", AssetMaintenanceEntered),
        ("exit_asset_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_drawing(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    drawing through from prior state."""
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        drawing=_SAMPLE_DRAWING,
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.drawing == _SAMPLE_DRAWING


@pytest.mark.unit
def test_evolve_relocate_preserves_drawing() -> None:
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        drawing=_SAMPLE_DRAWING,
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
    assert state.drawing == _SAMPLE_DRAWING


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition", "kwargs"),
    [
        ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
        ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
        ("degraded", AssetDegraded, {"reason": "x"}),
        ("faulted", AssetFaulted, {"reason": "x"}),
        ("restored", AssetRestored, {"reason": "x"}),
        ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    ],
)
def test_evolve_mutation_preserves_drawing(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        drawing=_SAMPLE_DRAWING,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.drawing == _SAMPLE_DRAWING


@pytest.mark.unit
def test_evolve_port_added_preserves_drawing() -> None:
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        drawing=_SAMPLE_DRAWING,
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=prior.id,
            port_name="x",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert state.drawing == _SAMPLE_DRAWING


@pytest.mark.unit
def test_evolve_port_removed_preserves_drawing() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        ports=frozenset({port}),
        drawing=_SAMPLE_DRAWING,
    )
    state = evolve(prior, AssetPortRemoved(asset_id=prior.id, port_name="x", occurred_at=_NOW))
    assert state.drawing == _SAMPLE_DRAWING


# ---------- model_id genesis + preservation across transitions ----------


@pytest.mark.unit
def test_evolve_register_with_model_id_carries_model_id_into_state() -> None:
    """Genesis: AssetRegistered with model_id set lands the binding on
    Asset.model_id. Lock A: model_id is set ONCE at register_asset time."""
    asset_id = uuid4()
    model_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            model_id=model_id,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.model_id == model_id


@pytest.mark.unit
def test_evolve_register_without_model_id_yields_none() -> None:
    """Additive-state pattern: registration without model_id yields
    Asset.model_id=None (permissive default)."""
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
    assert state.model_id is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_maintenance", AssetMaintenanceEntered),
        ("exit_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_model_id(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry model_id
    through from prior state. model_id is set ONCE at registration per
    Lock A and never changes post-genesis, but transition arms still
    must carry it forward like any other Asset field."""
    _ = name
    model_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        model_id=model_id,
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.model_id == model_id


@pytest.mark.unit
def test_evolve_relocate_preserves_model_id() -> None:
    """Hierarchy mutation also must preserve model_id."""
    old_parent = uuid4()
    new_parent = uuid4()
    model_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        model_id=model_id,
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
    assert state.model_id == model_id


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition", "kwargs"),
    [
        ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
        ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
        ("degraded", AssetDegraded, {"reason": "x"}),
        ("faulted", AssetFaulted, {"reason": "x"}),
        ("restored", AssetRestored, {"reason": "x"}),
        ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    ],
)
def test_evolve_mutation_preserves_model_id(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Mirror of test_evolve_mutation_preserves_drawing: every mutation
    arm carries model_id forward."""
    _ = name
    model_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        model_id=model_id,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.model_id == model_id


@pytest.mark.unit
def test_evolve_port_added_preserves_model_id() -> None:
    model_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        model_id=model_id,
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=prior.id,
            port_name="x",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert state.model_id == model_id


@pytest.mark.unit
def test_evolve_port_removed_preserves_model_id() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    model_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        ports=frozenset({port}),
        model_id=model_id,
    )
    state = evolve(prior, AssetPortRemoved(asset_id=prior.id, port_name="x", occurred_at=_NOW))
    assert state.model_id == model_id


@pytest.mark.unit
def test_fold_register_with_model_id_then_lifecycle_transitions_preserves_model_id() -> None:
    """End-to-end fold: register with model_id, then activate + enter
    maintenance + exit maintenance + decommission. The model_id binding
    survives the entire lifecycle path."""
    asset_id = uuid4()
    parent_id = uuid4()
    model_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
                model_id=model_id,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.model_id == model_id
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


# ---------- alternate_identifiers genesis + transition arms + preservation ----------


_SAMPLE_ALT_ID_A = AlternateIdentifier(
    kind=AlternateIdentifierKind.SERIAL_NUMBER, value="12345-ABC"
)
_SAMPLE_ALT_ID_B = AlternateIdentifier(
    kind=AlternateIdentifierKind.INVENTORY_NUMBER, value="APS-2BM-CAM-001"
)


@pytest.mark.unit
def test_evolve_asset_registered_defaults_alternate_identifiers_to_empty_frozenset() -> None:
    """Genesis: AssetRegistered without alternate_identifiers yields
    Asset.alternate_identifiers=empty frozenset via the event-side
    default (additive-payload pattern)."""
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
    assert state.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_evolve_asset_registered_carries_alternate_identifiers_into_state() -> None:
    """Lock D: when register_asset seeds alternate_identifiers, the
    evolver lands them on Asset.alternate_identifiers verbatim."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="X",
            tier="Unit",
            parent_id=uuid4(),
            occurred_at=_NOW,
            alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B}),
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B})


@pytest.mark.unit
def test_evolve_alternate_identifier_added_inserts_into_frozenset() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
    )
    state = evolve(
        prior,
        AssetAlternateIdentifierAdded(
            asset_id=asset_id,
            alternate_identifier=_SAMPLE_ALT_ID_A,
            occurred_at=_NOW,
        ),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A})


@pytest.mark.unit
def test_evolve_alternate_identifier_added_is_idempotent_at_evolver_layer() -> None:
    """Evolver does NOT enforce strict-not-idempotent; that's the
    decider's job. Frozenset union semantics: adding an already-present
    (kind, value) is a no-op at this layer."""
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A}),
    )
    state = evolve(
        prior,
        AssetAlternateIdentifierAdded(
            asset_id=asset_id,
            alternate_identifier=_SAMPLE_ALT_ID_A,
            occurred_at=_NOW,
        ),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A})


@pytest.mark.unit
def test_evolve_alternate_identifier_removed_drops_from_frozenset() -> None:
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B}),
    )
    state = evolve(
        prior,
        AssetAlternateIdentifierRemoved(
            asset_id=asset_id,
            alternate_identifier=_SAMPLE_ALT_ID_A,
            occurred_at=_NOW,
        ),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_B})


@pytest.mark.unit
def test_evolve_alternate_identifier_removed_is_idempotent_at_evolver_layer() -> None:
    """Same rationale as Added's idempotent-at-evolver pin."""
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        alternate_identifiers=frozenset(),
    )
    state = evolve(
        prior,
        AssetAlternateIdentifierRemoved(
            asset_id=asset_id,
            alternate_identifier=_SAMPLE_ALT_ID_A,
            occurred_at=_NOW,
        ),
    )
    assert state.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_evolve_alternate_identifier_added_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetAlternateIdentifierAdded(
                asset_id=uuid4(),
                alternate_identifier=_SAMPLE_ALT_ID_A,
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_alternate_identifier_removed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetAlternateIdentifierRemoved(
                asset_id=uuid4(),
                alternate_identifier=_SAMPLE_ALT_ID_A,
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_evolve_alternate_identifier_added_preserves_other_facets() -> None:
    """Alternate-identifier mutations must not touch lifecycle /
    condition / settings / capabilities / parent_id / ports / drawing
    / model_id."""
    asset_id = uuid4()
    parent = uuid4()
    cap = uuid4()
    model_id = uuid4()
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    drawing = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")
    prior = Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=parent,
        lifecycle=AssetLifecycle.MAINTENANCE,
        condition=AssetCondition.DEGRADED,
        family_ids=frozenset({cap}),
        settings={"k": 1},
        ports=frozenset({port}),
        drawing=drawing,
        model_id=model_id,
    )
    state = evolve(
        prior,
        AssetAlternateIdentifierAdded(
            asset_id=asset_id,
            alternate_identifier=_SAMPLE_ALT_ID_A,
            occurred_at=_NOW,
        ),
    )
    assert state.lifecycle is AssetLifecycle.MAINTENANCE
    assert state.condition is AssetCondition.DEGRADED
    assert state.family_ids == frozenset({cap})
    assert state.settings == {"k": 1}
    assert state.ports == frozenset({port})
    assert state.parent_id == parent
    assert state.drawing == drawing
    assert state.model_id == model_id


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_maintenance", AssetMaintenanceEntered),
        ("exit_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_alternate_identifiers(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    alternate_identifiers through from prior state. Constructing
    Asset(...) without explicitly passing alternate_identifiers would
    silently WIPE it to its default (empty frozenset). Same shape as
    the family_ids / ports / drawing / model_id preservation pins."""
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B}),
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B})


@pytest.mark.unit
def test_evolve_relocate_preserves_alternate_identifiers() -> None:
    """Hierarchy mutation also must preserve alternate_identifiers."""
    old_parent = uuid4()
    new_parent = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A}),
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
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A})


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition", "kwargs"),
    [
        ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
        ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
        ("degraded", AssetDegraded, {"reason": "x"}),
        ("faulted", AssetFaulted, {"reason": "x"}),
        ("restored", AssetRestored, {"reason": "x"}),
        ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    ],
)
def test_evolve_mutation_preserves_alternate_identifiers(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Mirror of test_evolve_mutation_preserves_drawing /
    test_evolve_mutation_preserves_model_id: every mutation arm
    carries alternate_identifiers forward."""
    _ = name
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A}),
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A})


@pytest.mark.unit
def test_evolve_port_added_preserves_alternate_identifiers() -> None:
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_B}),
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=prior.id,
            port_name="x",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_B})


@pytest.mark.unit
def test_evolve_port_removed_preserves_alternate_identifiers() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        ports=frozenset({port}),
        alternate_identifiers=frozenset({_SAMPLE_ALT_ID_A}),
    )
    state = evolve(
        prior,
        AssetPortRemoved(asset_id=prior.id, port_name="x", occurred_at=_NOW),
    )
    assert state.alternate_identifiers == frozenset({_SAMPLE_ALT_ID_A})


@pytest.mark.unit
def test_fold_register_then_add_then_remove_yields_empty_alternate_identifiers() -> None:
    """End-to-end fold: register -> add alt-id -> remove alt-id lands
    back at empty. Pin against the fold layer."""
    asset_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="X",
                tier="Unit",
                parent_id=uuid4(),
                occurred_at=_NOW,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetAlternateIdentifierAdded(
                asset_id=asset_id,
                alternate_identifier=_SAMPLE_ALT_ID_A,
                occurred_at=_NOW,
            ),
            AssetAlternateIdentifierRemoved(
                asset_id=asset_id,
                alternate_identifier=_SAMPLE_ALT_ID_A,
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.alternate_identifiers == frozenset()


@pytest.mark.unit
def test_fold_register_with_seed_then_lifecycle_transitions_preserves_alternate_identifiers() -> (
    None
):
    """End-to-end fold: register with seeded alternate_identifiers,
    then activate + enter maintenance + exit maintenance + decommission.
    The seed survives the entire lifecycle path."""
    asset_id = uuid4()
    parent_id = uuid4()
    seed = frozenset({_SAMPLE_ALT_ID_A, _SAMPLE_ALT_ID_B})
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                tier="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
                alternate_identifiers=seed,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.alternate_identifiers == seed
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_evolve_asset_owner_removed_preserves_lifecycle_timestamps() -> None:
    """Critical pin: AssetOwnerRemoved MUST carry `commissioned_at` and
    `decommissioned_at` through from prior state. The Asset evolver
    Critical Invariant docstring lists both fields as required
    carry-forward; constructing Asset(...) without explicitly passing
    them silently wipes them to None, corrupting PIDINST Property 11
    lifecycle dates on any Asset whose owners change."""
    commissioned = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
    decommissioned = datetime(2026, 5, 1, 17, 0, 0, tzinfo=UTC)
    owner_a = AssetOwner(name=AssetOwnerName("HZB"))
    owner_b = AssetOwner(name=AssetOwnerName("APS"))
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        owners=frozenset({owner_a, owner_b}),
        commissioned_at=commissioned,
        decommissioned_at=decommissioned,
    )
    state = evolve(
        prior,
        AssetOwnerRemoved(asset_id=prior.id, owner_name=owner_a.name, occurred_at=_NOW),
    )
    assert state.owners == frozenset({owner_b})
    assert state.commissioned_at == commissioned
    assert state.decommissioned_at == decommissioned


@pytest.mark.unit
def test_evolve_asset_attached_to_fixture_preserves_lifecycle_timestamps() -> None:
    """Critical pin: AssetAttachedToFixture MUST carry `commissioned_at`
    and `decommissioned_at` through from prior state. Same silent-data-
    loss shape as AssetOwnerRemoved. Pinned because attach is the
    primary mutation path during 2-BM deployment ceremony; losing the
    commission timestamp on attach would corrupt the PIDINST view for
    every fixture-bound Asset."""
    commissioned = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
    fixture_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        commissioned_at=commissioned,
    )
    state = evolve(
        prior,
        AssetAttachedToFixture(asset_id=prior.id, fixture_id=fixture_id, occurred_at=_NOW),
    )
    assert state.fixture_id == fixture_id
    assert state.commissioned_at == commissioned
    assert state.decommissioned_at is None


# ---------- controller_id genesis + transition arms + preservation ----------


@pytest.mark.unit
def test_evolve_register_with_controller_id_folds_to_state() -> None:
    """Genesis: AssetRegistered with controller_id folds to
    Asset.controller_id on the new state."""
    asset_id = uuid4()
    controller_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="Rotary",
            tier="Device",
            parent_id=uuid4(),
            occurred_at=_NOW,
            controller_id=controller_id,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.controller_id == controller_id


@pytest.mark.unit
def test_evolve_register_without_controller_id_yields_none() -> None:
    """Additive-state pattern: registration without controller_id yields
    Asset.controller_id=None (permissive default; the dominant case for
    stages whose controller is sealed in or otherwise un-modelled)."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="X",
            tier="Device",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.controller_id is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_maintenance", AssetMaintenanceEntered),
        ("exit_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_controller_id(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    controller_id through from prior state. controller_id is set ONCE
    at registration per the Lock A precedent from model_id, but
    transition arms still must carry it forward like any other Asset
    field. Silent-wipe risk is the dominant failure mode the design
    memo flagged: constructing Asset(...) without controller_id wipes
    the field to None on the next state transition."""
    _ = name
    controller_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        controller_id=controller_id,
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.controller_id == controller_id


@pytest.mark.unit
def test_evolve_relocate_preserves_controller_id() -> None:
    """Hierarchy mutation also must preserve controller_id."""
    old_parent = uuid4()
    new_parent = uuid4()
    controller_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        controller_id=controller_id,
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
    assert state.controller_id == controller_id


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition", "kwargs"),
    [
        ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
        ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
        ("degraded", AssetDegraded, {"reason": "x"}),
        ("faulted", AssetFaulted, {"reason": "x"}),
        ("restored", AssetRestored, {"reason": "x"}),
        ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    ],
)
def test_evolve_mutation_preserves_controller_id(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Mirror of test_evolve_mutation_preserves_model_id: every mutation
    arm carries controller_id forward."""
    _ = name
    controller_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        controller_id=controller_id,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.controller_id == controller_id


@pytest.mark.unit
def test_evolve_port_added_preserves_controller_id() -> None:
    controller_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        controller_id=controller_id,
    )
    state = evolve(
        prior,
        AssetPortAdded(
            asset_id=prior.id,
            port_name="x",
            direction="Input",
            signal_type="TTL",
            occurred_at=_NOW,
        ),
    )
    assert state.controller_id == controller_id


@pytest.mark.unit
def test_evolve_port_removed_preserves_controller_id() -> None:
    port = AssetPort(name="x", direction=PortDirection.INPUT, signal_type="TTL")
    controller_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        ports=frozenset({port}),
        controller_id=controller_id,
    )
    state = evolve(prior, AssetPortRemoved(asset_id=prior.id, port_name="x", occurred_at=_NOW))
    assert state.controller_id == controller_id


@pytest.mark.unit
def test_fold_register_with_controller_id_then_lifecycle_transitions_preserves_controller_id() -> (
    None
):
    """End-to-end fold: register with controller_id, then activate +
    enter maintenance + exit maintenance + decommission. The
    controller_id binding survives the entire lifecycle path."""
    asset_id = uuid4()
    parent_id = uuid4()
    controller_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="Rotary",
                tier="Device",
                parent_id=parent_id,
                occurred_at=_NOW,
                controller_id=controller_id,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.controller_id == controller_id
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


# ---------- located_in_enclosure_id genesis + transition preservation ----------


@pytest.mark.unit
def test_evolve_register_with_located_in_enclosure_id_folds_to_state() -> None:
    """Genesis: AssetRegistered with located_in_enclosure_id folds to
    Asset.located_in_enclosure_id on the new state."""
    asset_id = uuid4()
    located_in_enclosure_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="Aerotech_ABRS_rotary",
            tier="Device",
            parent_id=uuid4(),
            occurred_at=_NOW,
            located_in_enclosure_id=located_in_enclosure_id,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.located_in_enclosure_id == located_in_enclosure_id


@pytest.mark.unit
def test_evolve_register_without_located_in_enclosure_id_yields_none() -> None:
    """Additive-state pattern: registration without
    located_in_enclosure_id yields Asset.located_in_enclosure_id=None."""
    state = evolve(
        None,
        AssetRegistered(
            asset_id=uuid4(),
            name="X",
            tier="Device",
            parent_id=uuid4(),
            occurred_at=_NOW,
            commissioned_by=_TEST_ACTOR_ID,
        ),
    )
    assert state.located_in_enclosure_id is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition"),
    [
        ("activate", AssetActivated),
        ("decommission", AssetDecommissioned),
        ("enter_maintenance", AssetMaintenanceEntered),
        ("exit_maintenance", AssetMaintenanceExited),
    ],
)
def test_evolve_lifecycle_transition_preserves_located_in_enclosure_id(
    name: str,
    transition: type,
) -> None:
    """Critical pin: every lifecycle transition arm MUST carry
    located_in_enclosure_id through from prior state. Set ONCE at
    registration (Lock A precedent from controller_id), but transition
    arms still carry it forward; a silent wipe would drop the pointer on
    the next state transition."""
    _ = name
    located_in_enclosure_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=(
            AssetLifecycle.COMMISSIONED
            if transition is AssetActivated
            else AssetLifecycle.ACTIVE
            if transition is AssetMaintenanceEntered
            else AssetLifecycle.MAINTENANCE
            if transition is AssetMaintenanceExited
            else AssetLifecycle.ACTIVE
        ),
        located_in_enclosure_id=located_in_enclosure_id,
    )
    state = evolve(
        prior, transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition))
    )
    assert state.located_in_enclosure_id == located_in_enclosure_id


@pytest.mark.unit
def test_evolve_relocate_preserves_located_in_enclosure_id() -> None:
    """Hierarchy mutation also must preserve located_in_enclosure_id."""
    old_parent = uuid4()
    new_parent = uuid4()
    located_in_enclosure_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=old_parent,
        located_in_enclosure_id=located_in_enclosure_id,
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
    assert state.located_in_enclosure_id == located_in_enclosure_id


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "transition", "kwargs"),
    [
        ("family_added", AssetFamilyAdded, {"family_id": uuid4()}),
        ("family_removed", AssetFamilyRemoved, {"family_id": uuid4()}),
        ("degraded", AssetDegraded, {"reason": "x"}),
        ("faulted", AssetFaulted, {"reason": "x"}),
        ("restored", AssetRestored, {"reason": "x"}),
        ("settings_updated", AssetSettingsUpdated, {"settings": {"a": 1}}),
    ],
)
def test_evolve_mutation_preserves_located_in_enclosure_id(
    name: str,
    transition: type,
    kwargs: dict[str, object],
) -> None:
    """Mirror of test_evolve_mutation_preserves_controller_id: every
    mutation arm carries located_in_enclosure_id forward."""
    _ = name
    located_in_enclosure_id = uuid4()
    prior = Asset(
        id=uuid4(),
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        located_in_enclosure_id=located_in_enclosure_id,
    )
    state = evolve(
        prior,
        transition(asset_id=prior.id, occurred_at=_NOW, **_extra_kwargs_for(transition), **kwargs),
    )
    assert state.located_in_enclosure_id == located_in_enclosure_id


@pytest.mark.unit
def test_fold_register_with_located_in_enclosure_id_survives_lifecycle_path() -> None:
    """End-to-end fold: register with located_in_enclosure_id, then
    activate + enter/exit maintenance + decommission. The pointer
    survives the entire lifecycle path."""
    asset_id = uuid4()
    parent_id = uuid4()
    located_in_enclosure_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="Aerotech_ABRS_rotary",
                tier="Device",
                parent_id=parent_id,
                occurred_at=_NOW,
                located_in_enclosure_id=located_in_enclosure_id,
                commissioned_by=_TEST_ACTOR_ID,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceExited(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(
                asset_id=asset_id, occurred_at=_NOW, decommissioned_by=_TEST_ACTOR_ID
            ),
        ]
    )
    assert state is not None
    assert state.located_in_enclosure_id == located_in_enclosure_id
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED
