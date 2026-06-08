"""Unit tests for the `inspect_plan_binding` query handler.

Mirrors the `define_plan` handler test's seed pattern (the load
fan-out is the same: Practice -> Method -> Capability -> per-Asset
-> per-Family) but asserts on the returned `InspectPlanBindingView`
shape rather than emitted events.

Coverage targets:
  - MissingCapability (Method without capability_id) -> BindingStatus.MISSING_CAPABILITY
  - Satisfied (families + affordances both covered)
  - MissingFamilies
  - MissingAffordances
  - Both missing -> status=MISSING_FAMILIES, both fields populated
  - Asset condition + lifecycle surfaced (Degraded, Decommissioned)
  - NotFound cases: Practice, Asset, Capability, Family
  - Deny path
  - Wired Assets sorted deterministically
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AssetCondition,
    AssetLevel,
    AssetLifecycle,
    AssetNotFoundError,
)
from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetDecommissioned,
    AssetDegraded,
    AssetFamilyAdded,
    AssetFaulted,
    AssetMaintenanceEntered,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import (
    to_payload as asset_to_payload,
)
from cora.equipment.aggregates.family import Affordance, FamilyNotFoundError
from cora.equipment.aggregates.family.events import FamilyDefined
from cora.equipment.aggregates.family.events import (
    event_type_name as family_event_type_name,
)
from cora.equipment.aggregates.family.events import (
    to_payload as family_to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe import UnauthorizedError
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityDefined,
    CapabilityName,
    CapabilityNotFoundError,
    ExecutorShape,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.events import MethodDefined
from cora.recipe.aggregates.method.events import (
    event_type_name as method_event_type_name,
)
from cora.recipe.aggregates.method.events import (
    to_payload as method_to_payload,
)
from cora.recipe.aggregates.practice import PracticeNotFoundError
from cora.recipe.aggregates.practice.events import PracticeDefined
from cora.recipe.aggregates.practice.events import (
    event_type_name as practice_event_type_name,
)
from cora.recipe.aggregates.practice.events import (
    to_payload as practice_to_payload,
)
from cora.recipe.features import inspect_plan_binding
from cora.recipe.features.inspect_plan_binding import (
    BindingStatus,
    InspectPlanBinding,
)
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000000ff01")
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000ff02")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000ff03")
_FAMILY_ROTARY_ID = UUID("01900000-0000-7000-8000-00000000ff10")
_FAMILY_CAMERA_ID = UUID("01900000-0000-7000-8000-00000000ff11")
_ASSET_A_ID = UUID("01900000-0000-7000-8000-00000000ff20")
_ASSET_B_ID = UUID("01900000-0000-7000-8000-00000000ff21")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


# ---------- Direct event-seeding helpers ----------


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    expected_version: int,
    event_type: str,
    payload: dict[str, object],
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type,
        payload=payload,
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_method(
    store: InMemoryEventStore,
    method_id: UUID,
    *,
    needed_family_ids: frozenset[UUID] = frozenset(),
    capability_id: UUID | None = None,
) -> None:
    event = MethodDefined(
        method_id=method_id,
        name="Test Method",
        needed_family_ids=tuple(sorted(needed_family_ids, key=str)),
        capability_id=capability_id,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        expected_version=0,
        event_type=method_event_type_name(event),
        payload=method_to_payload(event),
        command_name="DefineMethod",
    )


async def _seed_practice(
    store: InMemoryEventStore,
    practice_id: UUID,
    *,
    method_id: UUID,
) -> None:
    event = PracticeDefined(
        practice_id=practice_id,
        name="Test Practice",
        method_id=method_id,
        site_id=uuid4(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Practice",
        stream_id=practice_id,
        expected_version=0,
        event_type=practice_event_type_name(event),
        payload=practice_to_payload(event),
        command_name="DefinePractice",
    )


async def _seed_capability(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    required_affordances: frozenset[Affordance] = frozenset(),
) -> None:
    event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.test").value,
        name=CapabilityName("Test").value,
        required_affordances=required_affordances,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        event_type=capability_event_type_name(event),
        payload=capability_to_payload(event),
        command_name="DefineCapability",
    )


async def _seed_family(
    store: InMemoryEventStore,
    family_id: UUID,
    *,
    name: str = "TestFamily",
    affordances: frozenset[Affordance] = frozenset(),
) -> None:
    event = FamilyDefined(
        family_id=family_id,
        name=name,
        affordances=affordances,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Family",
        stream_id=family_id,
        expected_version=0,
        event_type=family_event_type_name(event),
        payload=family_to_payload(event),
        command_name="DefineFamily",
    )


async def _seed_asset(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    name: str = "TestAsset",
    family_ids: frozenset[UUID] = frozenset(),
    degraded: bool = False,
    faulted: bool = False,
    decommissioned: bool = False,
    in_maintenance: bool = False,
) -> None:
    register_event = AssetRegistered(
        asset_id=asset_id,
        name=name,
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    await _append(
        store,
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        event_type=asset_event_type_name(register_event),
        payload=asset_to_payload(register_event),
        command_name="RegisterAsset",
    )
    version = 1
    for family_id in sorted(family_ids, key=str):
        family_event = AssetFamilyAdded(asset_id=asset_id, family_id=family_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(family_event),
            payload=asset_to_payload(family_event),
            command_name="AddAssetFamily",
        )
        version += 1
    if degraded:
        degraded_event = AssetDegraded(
            asset_id=asset_id, reason="test degradation", occurred_at=_NOW
        )
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(degraded_event),
            payload=asset_to_payload(degraded_event),
            command_name="DegradeAsset",
        )
        version += 1
    if faulted:
        faulted_event = AssetFaulted(asset_id=asset_id, reason="test fault", occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(faulted_event),
            payload=asset_to_payload(faulted_event),
            command_name="FaultAsset",
        )
        version += 1
    if in_maintenance:
        activate_event = AssetActivated(asset_id=asset_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(activate_event),
            payload=asset_to_payload(activate_event),
            command_name="ActivateAsset",
        )
        version += 1
        maint_event = AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(maint_event),
            payload=asset_to_payload(maint_event),
            command_name="EnterAssetMaintenance",
        )
        version += 1
    if decommissioned:
        dc_event = AssetDecommissioned(
            asset_id=asset_id, occurred_at=_NOW, decommissioned_by=ActorId(uuid4())
        )
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(dc_event),
            payload=asset_to_payload(dc_event),
            command_name="DecommissionAsset",
        )


# ---------- Tests ----------


@pytest.mark.unit
async def test_handler_returns_no_capability_status_when_method_has_no_capability() -> None:
    """Legacy-shape Method (capability_id=None) yields MISSING_CAPABILITY."""
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_CAPABILITY
    assert view.capability_id is None
    assert view.capability_required_affordances == frozenset()
    assert view.missing_affordances == frozenset()


@pytest.mark.unit
async def test_handler_returns_satisfied_when_families_and_affordances_covered() -> None:
    """Happy path: all needed families bound + all required affordances covered."""
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        _CAPABILITY_ID,
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
    )
    await _seed_family(
        store,
        _FAMILY_ROTARY_ID,
        affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
    )
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.SATISFIED
    assert view.missing_family_ids == frozenset()
    assert view.missing_affordances == frozenset()
    assert view.capability_id == _CAPABILITY_ID
    assert len(view.wired_assets) == 1
    assert view.wired_assets[0].contributed_affordances == frozenset(
        {Affordance.ROTATABLE, Affordance.MARKING}
    )


@pytest.mark.unit
async def test_handler_returns_missing_families_when_asset_lacks_family() -> None:
    """Asset bound but doesn't carry the Family the Method needs."""
    store = InMemoryEventStore()
    await _seed_capability(store, _CAPABILITY_ID)
    await _seed_family(store, _FAMILY_ROTARY_ID)
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset())  # no families
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_FAMILIES
    assert view.missing_family_ids == frozenset({_FAMILY_ROTARY_ID})
    assert view.missing_affordances == frozenset()  # capability has none required


@pytest.mark.unit
async def test_handler_returns_missing_affordances_when_family_lacks_affordance() -> None:
    """Families bound, but their affordances don't cover the requirement."""
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        _CAPABILITY_ID,
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
    )
    await _seed_family(store, _FAMILY_ROTARY_ID, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert view.missing_family_ids == frozenset()
    assert view.missing_affordances == frozenset({Affordance.MARKING})


@pytest.mark.unit
async def test_handler_populates_both_missing_sets_when_both_dimensions_fail() -> None:
    """Both families and affordances missing -> status=MISSING_FAMILIES but
    both fields visible so operator sees the whole picture."""
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        _CAPABILITY_ID,
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.RECORDING}),
    )
    await _seed_family(store, _FAMILY_ROTARY_ID, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_family(store, _FAMILY_CAMERA_ID, affordances=frozenset())
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID, _FAMILY_CAMERA_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    # Asset carries only the rotary Family -> camera Family missing AND
    # Recording affordance missing.
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_FAMILIES
    assert view.missing_family_ids == frozenset({_FAMILY_CAMERA_ID})
    assert view.missing_affordances == frozenset({Affordance.RECORDING})


@pytest.mark.unit
async def test_handler_surfaces_asset_condition_and_lifecycle() -> None:
    """Degraded and Decommissioned states are visible in the wired-Asset view."""
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, name="Camera-04", degraded=True)
    await _seed_asset(store, _ASSET_B_ID, name="RotaryStage-02", decommissioned=True)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset({_ASSET_A_ID, _ASSET_B_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    by_id = {wa.asset_id: wa for wa in view.wired_assets}
    assert by_id[_ASSET_A_ID].condition is AssetCondition.DEGRADED
    assert by_id[_ASSET_A_ID].lifecycle is AssetLifecycle.COMMISSIONED
    assert by_id[_ASSET_B_ID].condition is AssetCondition.NOMINAL
    assert by_id[_ASSET_B_ID].lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
async def test_handler_surfaces_faulted_condition() -> None:
    """Faulted condition propagates through to the wired-Asset view
    (mirrors Degraded but covers the AssetFaulted serialization branch)."""
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, name="HighSpeedCamera-01", faulted=True)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.wired_assets[0].condition is AssetCondition.FAULTED


@pytest.mark.unit
async def test_handler_surfaces_maintenance_lifecycle() -> None:
    """Maintenance lifecycle propagates through to the wired-Asset view
    (covers the AssetMaintenanceEntered serialization branch; Maintenance
    is Active-only-source, so seeds via AssetActivated first)."""
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, name="RotaryStage-99", in_maintenance=True)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.wired_assets[0].lifecycle is AssetLifecycle.MAINTENANCE


@pytest.mark.unit
async def test_handler_orders_wired_assets_deterministically() -> None:
    """wired_assets sorted by asset_id stringification for replay determinism."""
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID)
    await _seed_asset(store, _ASSET_B_ID)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset({_ASSET_B_ID, _ASSET_A_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    actual_ids = [wa.asset_id for wa in view.wired_assets]
    expected_ids = sorted([_ASSET_A_ID, _ASSET_B_ID], key=str)
    assert actual_ids == expected_ids


@pytest.mark.unit
async def test_handler_raises_practice_not_found_for_unknown_practice_id() -> None:
    store = InMemoryEventStore()
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(PracticeNotFoundError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_practice_points_at_missing_method() -> None:
    """Practice exists but the Method it references doesn't (corrupted
    upstream chain). Covers handler.py's MethodNotFoundError raise site
    that the other 4 NotFound tests don't exercise transitively."""
    store = InMemoryEventStore()
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)  # Method NOT seeded
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found_for_unknown_asset_id() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_method_points_at_missing_cap() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=_CAPABILITY_ID)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID)
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(CapabilityNotFoundError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_family_not_found_when_asset_references_missing_family() -> None:
    store = InMemoryEventStore()
    await _seed_capability(store, _CAPABILITY_ID)
    await _seed_method(store, _METHOD_ID, capability_id=_CAPABILITY_ID)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    # Asset bound to a family_id whose Family stream was never seeded.
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    store = InMemoryEventStore()
    await _seed_method(store, _METHOD_ID, capability_id=None)
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    deps = build_deps(now=_NOW, event_store=store, deny=True)
    handler = inspect_plan_binding.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_skips_candidate_lookup_when_pool_is_none() -> None:
    """In-memory deps (no pool) returns empty missing_affordance_candidates
    even when affordances are missing. Mirrors get_plan's pool-optional
    pattern: candidate enumeration is projection-backed and gracefully
    no-ops without a configured pool."""
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        _CAPABILITY_ID,
        required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
    )
    await _seed_family(store, _FAMILY_ROTARY_ID, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert view.missing_affordances == frozenset({Affordance.MARKING})
    # Pool is None -> candidate enumeration skipped.
    assert view.missing_affordance_candidates == ()


@pytest.mark.unit
async def test_handler_returns_empty_candidates_when_no_affordances_missing() -> None:
    """When binding is satisfied, missing_affordance_candidates is empty
    (no missing affordance to enumerate candidates for)."""
    store = InMemoryEventStore()
    await _seed_capability(
        store,
        _CAPABILITY_ID,
        required_affordances=frozenset({Affordance.ROTATABLE}),
    )
    await _seed_family(store, _FAMILY_ROTARY_ID, affordances=frozenset({Affordance.ROTATABLE}))
    await _seed_method(
        store,
        _METHOD_ID,
        needed_family_ids=frozenset({_FAMILY_ROTARY_ID}),
        capability_id=_CAPABILITY_ID,
    )
    await _seed_practice(store, _PRACTICE_ID, method_id=_METHOD_ID)
    await _seed_asset(store, _ASSET_A_ID, family_ids=frozenset({_FAMILY_ROTARY_ID}))
    deps = build_deps(now=_NOW, event_store=store)
    handler = inspect_plan_binding.bind(deps)

    view = await handler(
        InspectPlanBinding(practice_id=_PRACTICE_ID, asset_ids=frozenset({_ASSET_A_ID})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.SATISFIED
    assert view.missing_affordance_candidates == ()
