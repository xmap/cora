"""Unit tests for the `get_asset_integration_view` query handler.

Read-time composition slice; the handler assembles the integration-view
bundle by loading the Asset stream + each referenced Family stream +
querying the existing CautionLookup port + (with pool) the Capability
projection.

In-memory test mode: AlwaysQuietCautionLookup +
AlwaysEmptyCapabilityLookup both return [] so existing tests don't
need to seed Caution or Capability projection rows. A surface-
specific test injects a fake CapabilityLookup returning seeded
references to prove the port -> view mapping.

This file pins:
  - returns None on unknown asset id (route maps to 404)
  - happy path: Asset with no families → empty families + empty
    applicable_capabilities + empty active_cautions + incomplete=False
  - happy path: Asset with 2 families → families view carries name +
    affordances; combined affordances drive applicable_capabilities
    (empty under no-pool but the computation completes)
  - missing-family tolerance: Family in asset.family_ids with no events
    in the store → skip with warning + incomplete=True
  - Deny path: UnauthorizedError raised pre-load (no event-store reads)
  - wire registration: get_asset_integration_view appears on EquipmentHandlers
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.features import (
    add_asset_family,
    define_family,
    get_asset_integration_view,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_asset_integration_view import (
    AssetIntegrationView,
    GetAssetIntegrationView,
)
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.ports import CapabilityLookupResult
from tests.unit._helpers import build_deps as _build_deps

_NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)

# Sentinel UUIDs. The FixedIdGenerator consumes them in order:
# (1) asset id from register_asset, (2) AssetRegistered event id,
# (3) family-A id, (4) FamilyDefined event id for A,
# (5) family-B id, (6) FamilyDefined event id for B,
# (7,8) two AssetFamilyAdded event ids.
_ASSET_ID = UUID("01900000-0000-7000-8000-00000000b101")
_ASSET_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b102")
_FAMILY_A_ID = UUID("01900000-0000-7000-8000-00000000b201")
_FAMILY_A_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b202")
_FAMILY_B_ID = UUID("01900000-0000-7000-8000-00000000b301")
_FAMILY_B_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b302")
_ADD_FAMILY_A_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b401")
_ADD_FAMILY_B_EVENT_ID = UUID("01900000-0000-7000-8000-00000000b402")
_PARENT_ID = UUID("01900000-0000-7000-8000-00000000b001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_asset() -> None:
    deps = _build_deps(now=_NOW)
    handler = get_asset_integration_view.bind(deps)
    view = await handler(
        GetAssetIntegrationView(asset_id=_ASSET_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_returns_bundle_for_registered_asset_with_no_families() -> None:
    """Happy path with no families: bundle has empty families,
    empty active_cautions (AlwaysQuietCautionLookup), empty
    applicable_capabilities (no-pool path), incomplete=False."""
    deps = _build_deps(
        ids=[_ASSET_ID, _ASSET_REGISTERED_EVENT_ID],
        now=_NOW,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset_integration_view.bind(deps)
    view = await handler(
        GetAssetIntegrationView(asset_id=_ASSET_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert isinstance(view, AssetIntegrationView)
    assert view.asset_id == _ASSET_ID
    assert view.name == "APS-2BM"
    assert view.tier == "Unit"
    assert view.parent_id == _PARENT_ID
    assert view.lifecycle == "Commissioned"
    assert view.condition == "Nominal"
    assert view.families == ()
    assert view.ports == ()
    assert view.settings == {}
    assert view.active_cautions == ()
    assert view.applicable_capabilities == ()
    assert view.incomplete is False


@pytest.mark.unit
async def test_handler_returns_family_views_with_combined_affordances() -> None:
    """Happy path with 2 families: bundle families[] carries each
    Family's name + affordances; combined-affordances feeds the
    Capability filter (empty under no-pool but the load completes
    without error)."""
    deps = _build_deps(
        ids=[
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _FAMILY_A_ID,
            _FAMILY_A_DEFINED_EVENT_ID,
            _FAMILY_B_ID,
            _FAMILY_B_DEFINED_EVENT_ID,
            _ADD_FAMILY_A_EVENT_ID,
            _ADD_FAMILY_B_EVENT_ID,
        ],
        now=_NOW,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset({Affordance.POSABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset({Affordance.TRIGGERABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=_ASSET_ID, family_id=_FAMILY_A_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=_ASSET_ID, family_id=_FAMILY_B_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset_integration_view.bind(deps)
    view = await handler(
        GetAssetIntegrationView(asset_id=_ASSET_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert len(view.families) == 2
    family_ids = {f.family_id for f in view.families}
    assert family_ids == {_FAMILY_A_ID, _FAMILY_B_ID}
    # The 2 families carry their respective affordance sets (each as
    # a frozenset of Affordance enum string values).
    family_by_id = {f.family_id: f for f in view.families}
    assert family_by_id[_FAMILY_A_ID].name == "RotaryStage"
    assert family_by_id[_FAMILY_A_ID].affordances == frozenset({Affordance.POSABLE.value})
    assert family_by_id[_FAMILY_B_ID].name == "Camera"
    assert family_by_id[_FAMILY_B_ID].affordances == frozenset({Affordance.TRIGGERABLE.value})
    # Under no-pool, applicable_capabilities falls back to empty list.
    assert view.applicable_capabilities == ()
    assert view.incomplete is False


@pytest.mark.unit
async def test_handler_marks_incomplete_when_family_missing_from_store() -> None:
    """Missing-Family tolerance: a Family referenced in Asset.family_ids
    whose stream has no events triggers a warning log + sets
    incomplete=True. Mirrors promote_dataset peer-load tolerance."""
    missing_family_id = UUID("01900000-0000-7000-8000-00000000beef")
    deps = _build_deps(
        ids=[
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _ADD_FAMILY_A_EVENT_ID,
        ],
        now=_NOW,
    )
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # add_asset_family decider does NOT verify the Family stream exists
    # (per the eventual-consistency stance on cross-aggregate refs;
    # see Asset state.py:516-521). So we can add a family_id with no
    # backing stream and the handler must tolerate it.
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=_ASSET_ID, family_id=missing_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset_integration_view.bind(deps)
    view = await handler(
        GetAssetIntegrationView(asset_id=_ASSET_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.families == ()  # missing family skipped
    assert view.incomplete is True


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(now=_NOW, deny=True)
    handler = get_asset_integration_view.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetAssetIntegrationView(asset_id=_ASSET_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
def test_wire_equipment_includes_get_asset_integration_view() -> None:
    deps = _build_deps(now=_NOW)
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.get_asset_integration_view)


class _FakeCapabilityLookup:
    """Test stub returning seeded CapabilityReferences for the affordance
    filter. The handler under test passes its combined-affordance
    frozenset and gets back a fixed list; the test asserts the mapping
    onto CapabilityView preserves all four fields plus order."""

    def __init__(self, refs: list[CapabilityLookupResult]) -> None:
        self.refs = refs
        self.calls: list[frozenset[str]] = []

    async def find_applicable_by_affordances(
        self,
        affordances: frozenset[str],
    ) -> list[CapabilityLookupResult]:
        self.calls.append(affordances)
        return list(self.refs)


@pytest.mark.unit
async def test_handler_maps_capability_lookup_refs_into_view() -> None:
    """The handler calls capability_lookup with the combined Family
    affordances and maps each returned CapabilityLookupResult onto a
    public CapabilityView (capability_id, code, name, status)."""
    import dataclasses

    cap_a = UUID("01900000-0000-7000-8000-00000000ca01")
    cap_b = UUID("01900000-0000-7000-8000-00000000ca02")
    seeded = [
        CapabilityLookupResult(
            capability_id=cap_a, code="cora.capability.alpha", name="Alpha", status="Defined"
        ),
        CapabilityLookupResult(
            capability_id=cap_b, code="cora.capability.bravo", name="Bravo", status="Versioned"
        ),
    ]
    fake = _FakeCapabilityLookup(seeded)

    deps = _build_deps(
        ids=[
            _ASSET_ID,
            _ASSET_REGISTERED_EVENT_ID,
            _FAMILY_A_ID,
            _FAMILY_A_DEFINED_EVENT_ID,
            _ADD_FAMILY_A_EVENT_ID,
        ],
        now=_NOW,
    )
    deps = dataclasses.replace(deps, capability_lookup=fake)  # type: ignore[arg-type]
    await register_asset.bind(deps)(
        RegisterAsset(name="APS-2BM", tier=AssetTier.UNIT, parent_id=_PARENT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_family.bind(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset({Affordance.POSABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=_ASSET_ID, family_id=_FAMILY_A_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_asset_integration_view.bind(deps)
    view = await handler(
        GetAssetIntegrationView(asset_id=_ASSET_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert len(view.applicable_capabilities) == 2
    assert view.applicable_capabilities[0].capability_id == cap_a
    assert view.applicable_capabilities[0].code == "cora.capability.alpha"
    assert view.applicable_capabilities[0].name == "Alpha"
    assert view.applicable_capabilities[0].status == "Defined"
    assert view.applicable_capabilities[1].capability_id == cap_b
    assert view.applicable_capabilities[1].status == "Versioned"
    # The port was called with the Asset's combined Family affordances
    # (one Family with POSABLE in this scenario).
    assert fake.calls == [frozenset({Affordance.POSABLE.value})]
