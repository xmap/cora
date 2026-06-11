"""Unit tests for the `define_plan` slice's pure decider.

First decider in the codebase that takes upstream aggregate state
as input (`PlanBindingContext`). These tests exercise the decider
directly with hand-built contexts; handler-level integration tests
live in test_define_plan_handler.py.

Validation order pinned per gate-review Q5:
  1. State must be None (PlanAlreadyExistsError)
  2. asset_ids non-empty (PlanAssetsRequiredError)
  3. Practice not Deprecated (PlanBoundPracticeDeprecatedError)
  4. Method not Deprecated (PlanBoundMethodDeprecatedError)
  5. No bound Asset Decommissioned (PlanAssetDecommissionedError)
  6. Family superset (PlanFamiliesNotSatisfiedError)
  7. Name validation (InvalidPlanNameError)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
    ExecutorShape,
)
from cora.recipe.aggregates.method import Method, MethodName, MethodStatus
from cora.recipe.aggregates.plan import (
    InvalidPlanNameError,
    Plan,
    PlanAffordancesNotSatisfiedError,
    PlanAlreadyExistsError,
    PlanAssetDecommissionedError,
    PlanAssetsRequiredError,
    PlanBoundMethodDeprecatedError,
    PlanBoundPracticeDeprecatedError,
    PlanDefined,
    PlanFamiliesNotSatisfiedError,
    PlanName,
    PlanStatus,
)
from cora.recipe.aggregates.practice import (
    Practice,
    PracticeName,
    PracticeStatus,
)
from cora.recipe.features import define_plan
from cora.recipe.features.define_plan import DefinePlan, PlanBindingContext

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _practice(
    *,
    practice_id: UUID | None = None,
    method_id: UUID | None = None,
    site_id: UUID | None = None,
    status: PracticeStatus = PracticeStatus.DEFINED,
) -> Practice:
    return Practice(
        id=practice_id or uuid4(),
        name=PracticeName("APS XRF Fly Scan at 32-ID"),
        method_id=method_id or uuid4(),
        site_id=site_id or uuid4(),
        status=status,
    )


def _method(
    *,
    method_id: UUID | None = None,
    needed_family_ids: frozenset[UUID] | None = None,
    status: MethodStatus = MethodStatus.DEFINED,
) -> Method:
    return Method(
        id=method_id or uuid4(),
        name=MethodName("XRF Fly Scan Mapping"),
        needed_family_ids=needed_family_ids if needed_family_ids is not None else frozenset(),
        status=status,
    )


def _asset(
    *,
    asset_id: UUID | None = None,
    family_ids: frozenset[UUID] | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        name=AssetName("EigerDetector"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=family_ids if family_ids is not None else frozenset(),
    )


def _context(
    *,
    practice: Practice | None = None,
    method: Method | None = None,
    assets: dict[UUID, Asset] | None = None,
) -> PlanBindingContext:
    """Build a default-valid binding context, overrideable per test."""
    p = practice or _practice()
    m = method or _method()
    if assets is None:
        default_id = uuid4()
        assets = {default_id: _asset(asset_id=default_id)}
    return PlanBindingContext(practice=p, method=m, assets=assets)


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_plan_defined_for_valid_binding() -> None:
    """All checks pass: bound Assets satisfy Method's capabilities,
    upstream is non-Deprecated, asset is non-Decommissioned."""
    cap = uuid4()
    method = _method(needed_family_ids=frozenset({cap}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    new_id = uuid4()
    events = define_plan.decide(
        state=None,
        command=DefinePlan(
            name="32-ID FlyScan Plan",
            practice_id=practice.id,
            asset_ids=frozenset({asset_id}),
        ),
        context=context,
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        PlanDefined(
            plan_id=new_id,
            name="32-ID FlyScan Plan",
            practice_id=practice.id,
            asset_ids=(asset_id,),
            method_id=method.id,
            method_needed_family_ids_snapshot=(cap,),
            asset_families_snapshot={asset_id: (cap,)},
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_captures_method_id_in_event_for_audit() -> None:
    """method_id resolved transitively from practice.method_id and
    captured in the PlanDefined event payload as audit data
    (capture-don't-recompute principle)."""
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=DefinePlan(
            name="X",
            practice_id=practice.id,
            asset_ids=frozenset({asset_id}),
        ),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].method_id == method.id


@pytest.mark.unit
def test_decide_captures_asset_families_snapshot_at_bind_time() -> None:
    """gate-review Q4: snapshots in event payload pin what was true
    at bind time, even if Assets later evolve."""
    cap1 = uuid4()
    cap2 = uuid4()
    a1 = uuid4()
    a2 = uuid4()
    method = _method(needed_family_ids=frozenset({cap1, cap2}))
    practice = _practice(method_id=method.id)
    assets = {
        a1: _asset(asset_id=a1, family_ids=frozenset({cap1})),
        a2: _asset(asset_id=a2, family_ids=frozenset({cap2})),
    }
    context = PlanBindingContext(practice=practice, method=method, assets=assets)
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({a1, a2})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    snapshot = events[0].asset_families_snapshot
    assert snapshot[a1] == (cap1,)
    assert snapshot[a2] == (cap2,)


@pytest.mark.unit
def test_decide_trims_plan_name_via_value_object() -> None:
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="  X  ", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].name == "X"


# ---------- Validation: state pre-existing ----------


@pytest.mark.unit
def test_decide_raises_plan_already_exists_when_state_is_not_none() -> None:
    existing_id = uuid4()
    state = Plan(
        id=existing_id,
        name=PlanName("X"),
        practice_id=uuid4(),
        asset_ids=frozenset({uuid4()}),
        status=PlanStatus.DEFINED,
    )
    with pytest.raises(PlanAlreadyExistsError) as exc_info:
        define_plan.decide(
            state=state,
            command=DefinePlan(name="X", practice_id=uuid4(), asset_ids=frozenset({uuid4()})),
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.plan_id == existing_id


# ---------- Validation: empty asset_ids ----------


@pytest.mark.unit
def test_decide_raises_invalid_plan_for_empty_asset_ids() -> None:
    """A Plan with no Asset bindings is structurally meaningless."""
    with pytest.raises(PlanAssetsRequiredError):
        define_plan.decide(
            state=None,
            command=DefinePlan(name="X", practice_id=uuid4(), asset_ids=frozenset()),
            context=_context(),
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Validation: deprecated upstream ----------


@pytest.mark.unit
def test_decide_raises_practice_deprecated_when_practice_is_deprecated() -> None:
    practice = _practice(status=PracticeStatus.DEPRECATED)
    context = _context(practice=practice)
    with pytest.raises(PlanBoundPracticeDeprecatedError) as exc_info:
        define_plan.decide(
            state=None,
            command=DefinePlan(
                name="X",
                practice_id=practice.id,
                asset_ids=frozenset(context.assets.keys()),
            ),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.practice_id == practice.id


@pytest.mark.unit
def test_decide_raises_method_deprecated_when_method_is_deprecated() -> None:
    method = _method(status=MethodStatus.DEPRECATED)
    practice = _practice(method_id=method.id)
    context = _context(practice=practice, method=method)
    with pytest.raises(PlanBoundMethodDeprecatedError) as exc_info:
        define_plan.decide(
            state=None,
            command=DefinePlan(
                name="X",
                practice_id=practice.id,
                asset_ids=frozenset(context.assets.keys()),
            ),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.method_id == method.id


# ---------- Validation: decommissioned asset ----------


@pytest.mark.unit
def test_decide_raises_asset_decommissioned_when_any_bound_asset_is_decommissioned() -> None:
    a1 = uuid4()
    a2 = uuid4()
    a3 = uuid4()
    method = _method()
    practice = _practice(method_id=method.id)
    assets = {
        a1: _asset(asset_id=a1, lifecycle=AssetLifecycle.ACTIVE),
        a2: _asset(asset_id=a2, lifecycle=AssetLifecycle.DECOMMISSIONED),
        a3: _asset(asset_id=a3, lifecycle=AssetLifecycle.DECOMMISSIONED),
    }
    context = PlanBindingContext(practice=practice, method=method, assets=assets)
    with pytest.raises(PlanAssetDecommissionedError) as exc_info:
        define_plan.decide(
            state=None,
            command=DefinePlan(
                name="X",
                practice_id=practice.id,
                asset_ids=frozenset({a1, a2, a3}),
            ),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )
    # Carries the offending asset_ids (sorted).
    assert set(exc_info.value.asset_ids) == {a2, a3}


@pytest.mark.unit
def test_decide_accepts_commissioned_lifecycle_for_bound_assets() -> None:
    """Commissioned (pre-Active) is a valid binding target — assets
    that are spun up but not yet activated can still be bound."""
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.COMMISSIONED)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].plan_id is not None


# ---------- Validation: capability superset ----------


@pytest.mark.unit
def test_decide_raises_capabilities_not_satisfied_when_assets_missing_needed_capability() -> None:
    needed_cap = uuid4()
    different_cap = uuid4()
    method = _method(needed_family_ids=frozenset({needed_cap}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset({different_cap}))
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    with pytest.raises(PlanFamiliesNotSatisfiedError) as exc_info:
        define_plan.decide(
            state=None,
            command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.missing_family_ids == frozenset({needed_cap})


@pytest.mark.unit
def test_decide_uses_union_of_bound_assets_capabilities_for_satisfaction_check() -> None:
    """gate-review Q3: capability check is on UNION across all bound
    Assets, not per-Asset. A Method needing capabilities that are
    distributed across multiple Assets binds successfully."""
    cap1 = uuid4()
    cap2 = uuid4()
    method = _method(needed_family_ids=frozenset({cap1, cap2}))
    practice = _practice(method_id=method.id)
    a1 = uuid4()
    a2 = uuid4()
    # Each asset has only ONE of the two needed capabilities;
    # together they cover both.
    assets = {
        a1: _asset(asset_id=a1, family_ids=frozenset({cap1})),
        a2: _asset(asset_id=a2, family_ids=frozenset({cap2})),
    }
    context = PlanBindingContext(practice=practice, method=method, assets=assets)
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({a1, a2})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_assets_with_extra_capabilities_beyond_method_needs() -> None:
    """Superset check: bound Assets may have MORE capabilities than
    the Method needs (extras are fine)."""
    needed = uuid4()
    extra = uuid4()
    method = _method(needed_family_ids=frozenset({needed}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset({needed, extra}))
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_method_with_empty_needed_family_ids() -> None:
    """Procedural Methods (no equipment requirement) bind to any set
    of Assets without capability-check failure."""
    method = _method(needed_family_ids=frozenset())
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id, family_ids=frozenset())
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


# ---------- Validation: name ----------


@pytest.mark.unit
def test_decide_raises_invalid_plan_name_for_whitespace_only_name() -> None:
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    with pytest.raises(InvalidPlanNameError):
        define_plan.decide(
            state=None,
            command=DefinePlan(
                name="   ", practice_id=practice.id, asset_ids=frozenset({asset_id})
            ),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Determinism ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    method = _method()
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    asset = _asset(asset_id=asset_id)
    context = PlanBindingContext(practice=practice, method=method, assets={asset_id: asset})
    new_id = uuid4()
    cmd = DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id}))
    first = define_plan.decide(state=None, command=cmd, context=context, now=_NOW, new_id=new_id)
    second = define_plan.decide(state=None, command=cmd, context=context, now=_NOW, new_id=new_id)
    assert first == second


@pytest.mark.unit
def test_decide_emits_deterministic_asset_id_ordering_for_idempotency() -> None:
    """Same logical asset set in different iteration orders must
    produce the same event payload (idempotency-key hashing)."""
    method = _method()
    practice = _practice(method_id=method.id)
    a1 = uuid4()
    a2 = uuid4()
    a3 = uuid4()
    assets = {a: _asset(asset_id=a) for a in [a1, a2, a3]}
    context = PlanBindingContext(practice=practice, method=method, assets=assets)
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({a1, a2, a3})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].asset_ids == tuple(sorted([a1, a2, a3], key=str))


# ---------- Affordance-cover guard ----------


def _capability(
    *,
    required: frozenset[Affordance] = frozenset(),
    capability_id: UUID | None = None,
    status: CapabilityStatus = CapabilityStatus.DEFINED,
    version: str | None = None,
) -> Capability:
    """Build a Capability fixture for the affordance-cover guard."""
    return Capability(
        id=capability_id or uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        required_affordances=required,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        status=status,
        version=version,
    )


@pytest.mark.unit
def test_decide_skips_affordance_guard_when_context_capability_is_none() -> None:
    """Compat: when Method has no `capability_id`, the handler builds the
    context with capability=None and family_affordances={}. The decider must
    NOT raise even when Family.affordances is empty, because there's no
    contract to compare against. Pinned to lock the additive transition
    window."""
    family_id = uuid4()
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({family_id}))}
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=None,
        family_affordances={},
    )
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_binding_when_family_affordances_cover_capability_requirements() -> None:
    """Happy path: bound Asset's single Family declares an affordance set
    that covers the Capability's required affordances."""
    family_id = uuid4()
    capability = _capability(required=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}))
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({family_id}))}
    family_affordances = {
        family_id: frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE, Affordance.HOMEABLE})
    }
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=capability,
        family_affordances=family_affordances,
    )
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_raises_affordances_not_satisfied_when_union_misses_required() -> None:
    """Sad path: every needed Family is bound (the family-id check passes),
    but the union of Family.affordances misses one of
    `capability.required_affordances`. Raises
    PlanAffordancesNotSatisfiedError carrying the missing affordance string
    values."""
    family_id = uuid4()
    capability = _capability(required=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}))
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({family_id}))}
    family_affordances = {family_id: frozenset({Affordance.ROTATABLE})}  # missing TRIGGERABLE
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=capability,
        family_affordances=family_affordances,
    )
    with pytest.raises(PlanAffordancesNotSatisfiedError) as exc_info:
        define_plan.decide(
            state=None,
            command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.missing_affordances == frozenset({Affordance.TRIGGERABLE.value})


@pytest.mark.unit
def test_decide_unions_affordances_across_multiple_bound_assets() -> None:
    """The affordance-cover check unions across ALL bound Assets' Families.
    Two Assets each carrying one Family that contributes a distinct affordance
    together cover a 2-affordance Capability. Pinned because the union
    semantics mirror the existing family-id union (bound-Asset-only)."""
    fam_rot = uuid4()
    fam_trig = uuid4()
    capability = _capability(required=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}))
    method = _method(needed_family_ids=frozenset({fam_rot, fam_trig}))
    practice = _practice(method_id=method.id)
    a_rot = uuid4()
    a_trig = uuid4()
    assets = {
        a_rot: _asset(asset_id=a_rot, family_ids=frozenset({fam_rot})),
        a_trig: _asset(asset_id=a_trig, family_ids=frozenset({fam_trig})),
    }
    family_affordances = {
        fam_rot: frozenset({Affordance.ROTATABLE}),
        fam_trig: frozenset({Affordance.TRIGGERABLE}),
    }
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=capability,
        family_affordances=family_affordances,
    )
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({a_rot, a_trig})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_affordance_guard_runs_after_family_id_check() -> None:
    """Ordering invariant. The family-id check (#6) fires BEFORE the
    affordance-cover check (#7). When the operator binds Assets that miss a
    required Family entirely, they get the family-id error first, not the
    affordance error, since that's the more direct diagnostic. Pinned because
    reversing this order would surface "missing affordance X" when the real
    issue is "missing Family Y entirely"."""
    needed_family = uuid4()
    bound_family = uuid4()  # different from needed_family
    capability = _capability(required=frozenset({Affordance.ROTATABLE}))
    method = _method(needed_family_ids=frozenset({needed_family}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({bound_family}))}
    family_affordances = {bound_family: frozenset({Affordance.ROTATABLE})}
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=capability,
        family_affordances=family_affordances,
    )
    with pytest.raises(PlanFamiliesNotSatisfiedError):
        define_plan.decide(
            state=None,
            command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
            context=context,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Final-coverage gate-review watch items ----------


@pytest.mark.unit
def test_decide_uses_current_capability_state_when_versioned_between_method_and_plan() -> None:
    """The affordance-cover guard reads CURRENT Capability state per the
    eventual-consistency stance. When a Capability is versioned BETWEEN
    Method.define_method and Plan.define_plan, the guard MUST use the NEW
    required_affordances (the version-2 Capability the handler loaded at
    Plan-bind time), not whatever shape was current at Method-define time.

    Tested directly at the decider: pass a Versioned Capability with a fresh
    `required_affordances` set, the affordance union covers the NEW set, and
    the bind succeeds. Pinned because the handler's load-at-Plan-bind pattern
    is what makes this race resolvable without snapshots."""
    family_id = uuid4()
    # Capability moved from Defined → Versioned with a different
    # required_affordances set (the v2 shape). Decider must validate
    # against the CURRENT (v2) set, not whatever Method observed at
    # Method-define time.
    versioned_capability = _capability(
        required=frozenset({Affordance.ROTATABLE}),
        status=CapabilityStatus.VERSIONED,
        version="v2",
    )
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({family_id}))}
    family_affordances = {family_id: frozenset({Affordance.ROTATABLE})}
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=versioned_capability,
        family_affordances=family_affordances,
    )
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_method_bound_to_deprecated_capability() -> None:
    """Capability deprecation is ADVISORY at the BC layer; no cascade. A
    Method bound to a Deprecated Capability must still pass Plan.bind so
    existing recipes keep working until operators explicitly re-bind. Pinned
    because reversing this would break every Plan whose Method.capability_id
    points at a LOINC/AAS-precedent superseded Capability.

    Note: Deprecated Capabilities can still cover their affordance contract;
    they're soft-deprecated, not invalidated. Operators see the deprecation
    status via `get_capability` and choose when to re-bind."""
    family_id = uuid4()
    deprecated_capability = _capability(
        required=frozenset({Affordance.ROTATABLE}),
        status=CapabilityStatus.DEPRECATED,
        version="v1",
    )
    method = _method(needed_family_ids=frozenset({family_id}))
    practice = _practice(method_id=method.id)
    asset_id = uuid4()
    assets = {asset_id: _asset(asset_id=asset_id, family_ids=frozenset({family_id}))}
    family_affordances = {family_id: frozenset({Affordance.ROTATABLE})}
    context = PlanBindingContext(
        practice=practice,
        method=method,
        assets=assets,
        capability=deprecated_capability,
        family_affordances=family_affordances,
    )
    events = define_plan.decide(
        state=None,
        command=DefinePlan(name="X", practice_id=practice.id, asset_ids=frozenset({asset_id})),
        context=context,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1, "Deprecated Capability must NOT block Plan binding"
