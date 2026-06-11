"""Layer 3 sub-slice 3D: decider tests for the role_kind path of `bind_plan_role`.

Pins the ANY-single-family disjunction per Lock 17:
  - Asset.family_ids walked via context.family_lookups
  - bound iff AT LEAST ONE Family advertises role_kind in
    presents_as AND has affordances superset of
    role_lookup_result.required_affordances
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import Asset, AssetName
from cora.infrastructure.ports import (
    AssemblyLookupResult,
    FamilyLookupResult,
    RoleLookupResult,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    RoleName,
    RoleRequirement,
)
from cora.recipe.aggregates.plan import (
    Plan,
    PlanName,
    PlanRoleAssetCannotPresentError,
    PlanRoleBound,
    PlanRoleFamilyNotResolvableError,
    PlanStatus,
    RoleBinding,
    Wire,
)
from cora.recipe.features import bind_plan_role
from cora.recipe.features.bind_plan_role import BindPlanRole, BindPlanRoleContext

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _plan(
    *,
    asset_id: UUID,
    method_id: UUID,
) -> Plan:
    return Plan(
        id=uuid4(),
        name=PlanName("p"),
        practice_id=uuid4(),
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
        method_id=method_id,
        role_bindings=frozenset[RoleBinding](),
        wires=frozenset[Wire](),
    )


def _method(method_id: UUID, *, role_name: str, role_kind: UUID) -> Method:
    return Method(
        id=method_id,
        name=MethodName("m"),
        required_roles=frozenset(
            {RoleRequirement(role_name=RoleName(role_name), role_kind=role_kind)}
        ),
    )


def _asset(
    asset_id: UUID,
    *,
    family_ids: frozenset[UUID],
    fixture_id: UUID | None = None,
) -> Asset:
    from cora.equipment.aggregates.asset import AssetTier

    return Asset(
        id=asset_id,
        name=AssetName("a"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        family_ids=family_ids,
        ports=frozenset(),
        fixture_id=fixture_id,
    )


def _role_lookup(role_id: UUID, *, required: frozenset[str]) -> RoleLookupResult:
    return RoleLookupResult(
        id=role_id,
        name="X",
        required_affordances=required,
        optional_affordances=frozenset(),
    )


def _family_lookup(
    family_id: UUID, *, presents_as: frozenset[UUID], affordances: frozenset[str]
) -> FamilyLookupResult:
    return FamilyLookupResult(
        id=family_id,
        name="X",
        status="Defined",
        affordances=affordances,
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_role_kind_path_succeeds_when_single_family_satisfies() -> None:
    """ANY-single-family disjunction: only one Family on the Asset needs
    to advertise the Role AND cover its required_affordances."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),
        )
    }
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
        ),
        now=_NOW,
    )
    assert events == [
        PlanRoleBound(plan_id=state.id, role_name="detector", asset_id=aid, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_role_kind_path_disjunction_accepts_when_one_of_many_satisfies() -> None:
    """Asset carries 3 Families; only one advertises the Role -> still satisfies."""
    aid = uuid4()
    mid = uuid4()
    fid_advertising = uuid4()
    fid_other_a = uuid4()
    fid_other_b = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(
        aid,
        family_ids=frozenset({fid_advertising, fid_other_a, fid_other_b}),
    )
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid_advertising: _family_lookup(
            fid_advertising,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),
        ),
        fid_other_a: _family_lookup(fid_other_a, presents_as=frozenset(), affordances=frozenset()),
        fid_other_b: _family_lookup(fid_other_b, presents_as=frozenset(), affordances=frozenset()),
    }
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_no_family_advertises_role() -> None:
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset(),  # Family does NOT advertise this Role
            affordances=frozenset({"Imageable"}),
        )
    }
    with pytest.raises(PlanRoleAssetCannotPresentError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
            ),
            now=_NOW,
        )
    assert exc.value.role_kind == rid
    assert exc.value.asset_id == aid


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_family_advertises_but_lacks_affordances() -> None:
    """Family advertises the Role but is missing a required_affordance."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable", "Streamable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),  # missing Streamable
        )
    }
    with pytest.raises(PlanRoleAssetCannotPresentError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_family_lookup_misses() -> None:
    """An Asset.family_ids member that doesn't resolve via FamilyLookup."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="detector", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}))
    role_lookup = _role_lookup(rid, required=frozenset())
    # family_lookups dict empty -> the only family_id on the Asset is missing.
    with pytest.raises(PlanRoleFamilyNotResolvableError) as exc:
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("detector"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups={},
            ),
            now=_NOW,
        )
    assert exc.value.missing_family_id == fid


# ---- Assembly satisfaction OR-branch (BLOCKER #5 fix) ----------------------
#
# When the candidate Asset carries `fixture_id`, the handler loads the
# Fixture + AssemblyLookup; the decider ORs `role_kind in assembly.presents_as`
# on top of the Family disjunction. The Assembly path does NOT enforce the
# affordance-superset check at this layer (per 3C state.py docstring:
# Assembly affordances derive from the constituent Family union at
# register_fixture time, not Assembly template time).


def _assembly_lookup(assembly_id: UUID, *, presents_as: frozenset[UUID]) -> AssemblyLookupResult:
    return AssemblyLookupResult(
        id=assembly_id,
        name="MCTOptics",
        status="Defined",
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_role_kind_path_succeeds_via_assembly_when_no_family_satisfies() -> None:
    """MCTOptics worked example: Asset has Family that does NOT advertise the
    Role, but the Asset is part of an Assembly that DOES advertise it."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    fxid = uuid4()
    asmid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="imager", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}), fixture_id=fxid)
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset(),  # Family does NOT advertise
            affordances=frozenset(),
        )
    }
    assembly = _assembly_lookup(asmid, presents_as=frozenset({rid}))
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("imager"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
            assembly_lookup_result=assembly,
        ),
        now=_NOW,
    )
    assert events == [
        PlanRoleBound(plan_id=state.id, role_name="imager", asset_id=aid, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_role_kind_path_assembly_branch_skips_affordance_superset() -> None:
    """Assembly satisfaction does NOT enforce affordance-superset at bind time.

    Per the 3C state.py docstring the Assembly affordances derive at
    register_fixture time from the constituent Family union; the check
    belongs at that layer, not here. The Role's required_affordances are
    NOT checked against the Assembly row.
    """
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    fxid = uuid4()
    asmid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="imager", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}), fixture_id=fxid)
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable", "Streamable"}))
    family_lookups = {fid: _family_lookup(fid, presents_as=frozenset(), affordances=frozenset())}
    assembly = _assembly_lookup(asmid, presents_as=frozenset({rid}))
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("imager"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
            assembly_lookup_result=assembly,
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_neither_family_nor_assembly_satisfies() -> None:
    """Asset is in a Fixture but neither Family nor Assembly advertises the Role."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    fxid = uuid4()
    asmid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="imager", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}), fixture_id=fxid)
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset(),
            affordances=frozenset({"Imageable"}),
        )
    }
    assembly = _assembly_lookup(asmid, presents_as=frozenset())  # also empty
    with pytest.raises(PlanRoleAssetCannotPresentError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("imager"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
                assembly_lookup_result=assembly,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_role_kind_path_skips_assembly_branch_when_family_already_satisfies() -> None:
    """Short-circuit: when a Family satisfies, the Assembly branch is not consulted.

    The Assembly lookup is None here; if the Family branch did not
    short-circuit on success, the decider would proceed to the
    Assembly branch and not crash on None (the `is not None` guard
    handles it). This test asserts the success path is the Family
    branch, not the Assembly one.
    """
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    fxid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="imager", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}), fixture_id=fxid)
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset({rid}),
            affordances=frozenset({"Imageable"}),
        )
    }
    events = bind_plan_role.decide(
        state=state,
        command=BindPlanRole(plan_id=state.id, role_name=RoleName("imager"), asset_id=aid),
        context=BindPlanRoleContext(
            method=method,
            asset=asset,
            role_lookup_result=role_lookup,
            family_lookups=family_lookups,
            assembly_lookup_result=None,  # Family branch satisfies; Assembly not needed
        ),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_role_kind_path_raises_when_asset_not_in_fixture_and_family_misses() -> None:
    """Asset.fixture_id is None: the Assembly branch is skipped even if
    assembly_lookup_result is passed. Pins the `asset.fixture_id is not None`
    guard."""
    aid = uuid4()
    mid = uuid4()
    fid = uuid4()
    asmid = uuid4()
    rid = uuid4()
    state = _plan(asset_id=aid, method_id=mid)
    method = _method(mid, role_name="imager", role_kind=rid)
    asset = _asset(aid, family_ids=frozenset({fid}), fixture_id=None)
    role_lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    family_lookups = {
        fid: _family_lookup(
            fid,
            presents_as=frozenset(),
            affordances=frozenset({"Imageable"}),
        )
    }
    assembly = _assembly_lookup(asmid, presents_as=frozenset({rid}))
    with pytest.raises(PlanRoleAssetCannotPresentError):
        bind_plan_role.decide(
            state=state,
            command=BindPlanRole(plan_id=state.id, role_name=RoleName("imager"), asset_id=aid),
            context=BindPlanRoleContext(
                method=method,
                asset=asset,
                role_lookup_result=role_lookup,
                family_lookups=family_lookups,
                assembly_lookup_result=assembly,
            ),
            now=_NOW,
        )
