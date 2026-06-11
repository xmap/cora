"""Integration test: inspect_plan_binding handler against real Postgres.

Five tests:
- Satisfied path: full cross-BC load fan-out (Practice -> Method ->
  Capability -> per-Asset -> per-Family) against the real PG event
  store. No projection involved for the core diagnostic.
- Single-missing-affordance candidates: drains projections + verifies
  the per-missing-affordance enumeration returns sorted candidates
  excluding the wired Asset with contributing-family narrowing.
- Multi-missing-affordance candidates: a Family declaring both missing
  affordances surfaces its Asset in both entries; pins affordance-sort
  determinism + cache short-circuit.
- Empty candidates for an affordance with no contributing Family in
  the facility: the affordance still appears with `candidates=()`.
- Degraded candidate state: a Degraded candidate's condition surfaces
  unfiltered through the view (operator-decides contract).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.asset import AssetCondition, AssetLifecycle, AssetTier
from cora.equipment.aggregates.family import Affordance
from cora.equipment.features import (
    add_asset_family,
    define_family,
    degrade_asset,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.degrade_asset import DegradeAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.features import (
    define_capability,
    define_method,
    define_practice,
    inspect_plan_binding,
)
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.inspect_plan_binding import (
    BindingStatus,
    InspectPlanBinding,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 27, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_inspect_plan_binding_returns_satisfied_against_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: seed full chain via real handlers + verify diagnostic."""
    ids = [uuid4() for _ in range(20)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset({Affordance.ROTATABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    capability_id = await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.inspect_test",
            name="Inspect Test",
            required_affordances=frozenset({Affordance.ROTATABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Camera-04",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    view = await inspect_plan_binding.bind(deps)(
        InspectPlanBinding(practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.SATISFIED
    assert view.missing_family_ids == frozenset()
    assert view.missing_affordances == frozenset()
    assert view.capability_id == capability_id
    assert view.method_id == method_id
    assert len(view.wired_assets) == 1
    wired = view.wired_assets[0]
    assert wired.asset_id == asset_id
    assert wired.asset_name == "Camera-04"
    assert wired.contributed_affordances == frozenset({Affordance.ROTATABLE})


@pytest.mark.integration
async def test_inspect_plan_binding_enumerates_candidates_for_missing_affordance(
    db_pool: asyncpg.Pool,
) -> None:
    """Plan that's missing one affordance + 2 other facility Assets that
    could cover it -> view enumerates both candidates, sorted, with
    contributing-family narrowing, excluding the wired Asset."""
    ids = [uuid4() for _ in range(40)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    # Wired Family covers Rotatable only; the Method's Capability needs
    # Rotatable + Marking, so Marking is the missing affordance.
    wired_family_id = await define_family.bind(deps)(
        DefineFamily(
            name="RotaryOnly",
            affordances=frozenset({Affordance.ROTATABLE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Two other facility Families both declare Marking; one also has
    # Rotatable (so the candidate narrowing should drop Rotatable from
    # `family_ids` and keep only the Marking-declaring Family).
    marking_only_family_id = await define_family.bind(deps)(
        DefineFamily(
            name="MarkingOnly",
            affordances=frozenset({Affordance.MARKING}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    full_coverage_family_id = await define_family.bind(deps)(
        DefineFamily(
            name="FullCoverage",
            affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    capability_id = await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.inspect_test_candidates",
            name="Inspect Test Candidates",
            required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset({wired_family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    wired_asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Wired-Rotary",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=wired_asset_id, family_id=wired_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    candidate_a_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="MarkingPandA",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=candidate_a_id, family_id=marking_only_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    candidate_b_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="FullCoverageStage",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=candidate_b_id, family_id=full_coverage_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Drain projections so the candidate lookup sees the membership rows
    # + the family summary rows it iterates.
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await inspect_plan_binding.bind(deps)(
        InspectPlanBinding(
            practice_id=practice_id,
            asset_ids=frozenset({wired_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert view.missing_affordances == frozenset({Affordance.MARKING})
    assert len(view.missing_affordance_candidates) == 1
    entry = view.missing_affordance_candidates[0]
    assert entry.affordance is Affordance.MARKING
    # Two candidates, sorted by asset_id::text. Wired Asset is excluded.
    candidate_ids = [c.asset_id for c in entry.candidates]
    assert candidate_ids == sorted([candidate_a_id, candidate_b_id], key=str)
    assert wired_asset_id not in candidate_ids
    # Narrowing: each candidate's `contributing_family_ids` lists only
    # the Families that declare the missing affordance (Marking).
    by_id = {c.asset_id: c for c in entry.candidates}
    assert by_id[candidate_a_id].contributing_family_ids == frozenset({marking_only_family_id})
    assert by_id[candidate_b_id].contributing_family_ids == frozenset({full_coverage_family_id})
    # Per-candidate state surfaces (Nominal/Commissioned by default;
    # asserted explicitly so the view's "operator can see condition+
    # lifecycle" contract is exercised, not just the docstring).
    assert by_id[candidate_a_id].asset_name == "MarkingPandA"
    assert by_id[candidate_a_id].condition is AssetCondition.NOMINAL
    assert by_id[candidate_a_id].lifecycle is AssetLifecycle.COMMISSIONED
    assert by_id[candidate_b_id].asset_name == "FullCoverageStage"
    assert by_id[candidate_b_id].condition is AssetCondition.NOMINAL
    assert by_id[candidate_b_id].lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.integration
async def test_inspect_plan_binding_enumerates_candidates_for_multiple_missing_affordances(
    db_pool: asyncpg.Pool,
) -> None:
    """Capability needs Rotatable + Marking; nothing wired; one Family
    declares both. The candidate Asset appears in BOTH entries; the
    `_get_asset` cache short-circuits the second load. Asserts
    affordance-sort determinism + per-entry contributing-family
    narrowing across multiple missing affordances."""
    ids = [uuid4() for _ in range(20)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    full_coverage_family_id = await define_family.bind(deps)(
        DefineFamily(
            name="FullCoverage",
            affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    capability_id = await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.multi_missing",
            name="Multi Missing",
            required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # No wired Asset; both Rotatable + Marking are missing.
    candidate_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="FullStage",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=candidate_id, family_id=full_coverage_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    bystander_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Bystander",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await inspect_plan_binding.bind(deps)(
        InspectPlanBinding(
            practice_id=practice_id,
            asset_ids=frozenset({bystander_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert view.missing_affordances == frozenset({Affordance.ROTATABLE, Affordance.MARKING})
    # Two entries, sorted by affordance value (Marking < Rotatable
    # lexicographically). Same candidate appears in both, via the
    # same single contributing Family.
    affordances_in_order = [e.affordance for e in view.missing_affordance_candidates]
    assert affordances_in_order == [Affordance.MARKING, Affordance.ROTATABLE]
    for entry in view.missing_affordance_candidates:
        assert len(entry.candidates) == 1
        assert entry.candidates[0].asset_id == candidate_id
        assert entry.candidates[0].contributing_family_ids == frozenset({full_coverage_family_id})


@pytest.mark.integration
async def test_inspect_plan_binding_returns_empty_candidates_when_no_facility_family_declares_it(
    db_pool: asyncpg.Pool,
) -> None:
    """A missing affordance declared by no facility Family still
    appears in `missing_affordance_candidates` with empty
    `candidates=()`. Pins the contract: 'we looked, found nothing'
    is distinct from 'affordance not enumerated'."""
    ids = [uuid4() for _ in range(15)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    # Only one Family in the facility; it declares Rotatable only.
    rotary_family_id = await define_family.bind(deps)(
        DefineFamily(name="Rotary", affordances=frozenset({Affordance.ROTATABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Capability needs Rotatable + Marking; Marking has no
    # contributing Family anywhere.
    capability_id = await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.no_marking_anywhere",
            name="No Marking Anywhere",
            required_affordances=frozenset({Affordance.ROTATABLE, Affordance.MARKING}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset({rotary_family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    wired_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="WiredRotary",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=wired_id, family_id=rotary_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await inspect_plan_binding.bind(deps)(
        InspectPlanBinding(
            practice_id=practice_id,
            asset_ids=frozenset({wired_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert view.missing_affordances == frozenset({Affordance.MARKING})
    assert len(view.missing_affordance_candidates) == 1
    entry = view.missing_affordance_candidates[0]
    assert entry.affordance is Affordance.MARKING
    # Affordance is still enumerated, but with zero candidates.
    assert entry.candidates == ()


@pytest.mark.integration
async def test_inspect_plan_binding_surfaces_degraded_candidate_state(
    db_pool: asyncpg.Pool,
) -> None:
    """A Degraded candidate Asset surfaces in the diagnostic with
    its condition unfiltered. Pins the view's 'operator can see
    Faulted/Decommissioned candidates' contract end-to-end."""
    ids = [uuid4() for _ in range(15)]
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)

    marking_family_id = await define_family.bind(deps)(
        DefineFamily(name="MarkingFamily", affordances=frozenset({Affordance.MARKING})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    capability_id = await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.degraded_candidate",
            name="Degraded Candidate",
            required_affordances=frozenset({Affordance.MARKING}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    bystander_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="Bystander",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    degraded_candidate_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="TouchyPandA",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=degraded_candidate_id, family_id=marking_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await degrade_asset.bind(deps)(
        DegradeAsset(
            asset_id=degraded_candidate_id,
            reason="intermittent encoder glitch",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    view = await inspect_plan_binding.bind(deps)(
        InspectPlanBinding(
            practice_id=practice_id,
            asset_ids=frozenset({bystander_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view.binding_status is BindingStatus.MISSING_AFFORDANCES
    assert len(view.missing_affordance_candidates) == 1
    entry = view.missing_affordance_candidates[0]
    assert len(entry.candidates) == 1
    candidate = entry.candidates[0]
    assert candidate.asset_id == degraded_candidate_id
    # Degraded condition surfaces; operator sees the state and decides.
    assert candidate.condition is AssetCondition.DEGRADED
    assert candidate.lifecycle is AssetLifecycle.COMMISSIONED
