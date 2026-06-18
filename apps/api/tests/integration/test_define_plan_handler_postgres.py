"""End-to-end integration test: define_plan handler against real Postgres.

Pinned: cross-aggregate pre-loads (gate-review Q5) work against
real event-store streams. The handler reads Practice → Method →
Asset events from Postgres, builds a PlanBindingContext, and
persists the resulting PlanDefined event with audit snapshots.

This is the first integration test that exercises a handler
loading aggregates from MULTIPLE other BCs (Recipe loading
Equipment.Asset; Recipe loading Recipe.Method via Recipe.Practice).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import Affordance, FamilyName, family_stream_id
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.aggregates.plan import (
    PlanAffordancesNotSatisfiedError,
    PlanName,
    PlanStatus,
    load_plan,
)
from cora.recipe.features import (
    define_capability,
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_capability import DefineCapability
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_plan_persists_event_with_audit_snapshots_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    # Pre-allocate UUIDs in the order handlers will consume them.
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000060aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000060ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000060ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000060ab03")
    method_id = UUID("01900000-0000-7000-8000-00000060ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000060ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000060ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000060ad02")
    site_id = UUID("01900000-0000-7000-8000-00000060ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000060af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000060af02")

    # event-store API (bypasses the FixedIdGenerator queue).
    method_capability_id = UUID("01900000-0000-7000-8000-00000060a0cc")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            cap_event_id,
            asset_id,
            asset_register_event_id,
            asset_addcap_event_id,
            method_id,
            method_event_id,
            practice_id,
            practice_event_id,
            plan_id,
            plan_event_id,
        ],
    )

    # Seed upstream chain: Family → Asset(+capability) → Method → Practice.
    await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(
        deps.event_store, method_capability_id, shapes=frozenset({ExecutorShape.METHOD})
    )
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Fly Scan Mapping",
            capability_id=method_capability_id,
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(
            name="APS XRF Fly Scan at 32-ID",
            method_id=method_id,
            site_id=site_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Now define the Plan — the cross-aggregate pre-loads must read
    # Practice/Method/Asset back from Postgres.
    returned_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan Plan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == plan_id

    # Verify the persisted event payload (including audit snapshots).
    events, version = await deps.event_store.load("Plan", plan_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "PlanDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "plan_id": str(plan_id),
        "name": "32-ID FlyScan Plan",
        "practice_id": str(practice_id),
        "asset_ids": [str(asset_id)],
        "method_id": str(method_id),
        "method_needed_family_ids_snapshot": [str(cap_id)],
        "asset_families_snapshot": {str(asset_id): [str(cap_id)]},
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.event_id == plan_event_id
    assert stored.metadata == {"command": "DefinePlan"}

    # Round-trip via load_plan: state should reconstruct exactly.
    plan = await load_plan(deps.event_store, plan_id)
    assert plan is not None
    assert plan.id == plan_id
    assert plan.name == PlanName("32-ID FlyScan Plan")
    assert plan.practice_id == practice_id
    assert plan.asset_ids == frozenset({asset_id})
    assert plan.status is PlanStatus.DEFINED


@pytest.mark.integration
async def test_define_plan_affordance_cover_guard_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """PG round-trip (gate-review P1): exercises the full
    cross-BC fan-out against real Postgres (Capability + Family +
    Asset + Method (with capability_id) + Practice + Plan) and asserts
    that the affordance-cover guard fires when Family.affordances
    miss a required affordance. Pinned because the fan-out reads
    Family streams across the BC boundary via load_family, and
    affordance set membership round-trips through jsonb."""
    cap_template_id = UUID("01900000-0000-7000-8000-00000061a001")
    cap_template_event = UUID("01900000-0000-7000-8000-00000061a002")
    family_id = family_stream_id(FamilyName("RotaryStage"))
    family_event = UUID("01900000-0000-7000-8000-00000061b002")
    asset_id = UUID("01900000-0000-7000-8000-00000061c001")
    asset_register_event = UUID("01900000-0000-7000-8000-00000061c002")
    asset_addcap_event = UUID("01900000-0000-7000-8000-00000061c003")
    method_id = UUID("01900000-0000-7000-8000-00000061d001")
    method_event = UUID("01900000-0000-7000-8000-00000061d002")
    practice_id = UUID("01900000-0000-7000-8000-00000061e001")
    practice_event = UUID("01900000-0000-7000-8000-00000061e002")
    site_id = UUID("01900000-0000-7000-8000-00000061f001")
    plan_id = UUID("01900000-0000-7000-8000-00000061faa1")
    plan_event = UUID("01900000-0000-7000-8000-00000061faa2")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            cap_template_id,
            cap_template_event,
            family_event,
            asset_id,
            asset_register_event,
            asset_addcap_event,
            method_id,
            method_event,
            practice_id,
            practice_event,
            plan_id,
            plan_event,
        ],
    )

    # Capability template requires ROTATABLE + TRIGGERABLE.
    await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.flyscan",
            name="FlyScan",
            required_affordances=frozenset({Affordance.ROTATABLE, Affordance.TRIGGERABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Family carries ONLY ROTATABLE — TRIGGERABLE is the missing
    # affordance that 6l.B's guard must surface.
    await define_family.bind(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset({Affordance.ROTATABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector",
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
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="FlyScan Method",
            needed_family_ids=frozenset({family_id}),
            capability_id=cap_template_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(
            name="APS FlyScan at 32-ID",
            method_id=method_id,
            site_id=site_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(PlanAffordancesNotSatisfiedError) as exc_info:
        await define_plan.bind(deps)(
            DefinePlan(
                name="32-ID FlyScan Plan",
                practice_id=practice_id,
                asset_ids=frozenset({asset_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.missing_affordances == frozenset({Affordance.TRIGGERABLE.value})

    # No Plan was persisted — the guard fired before any append.
    events, version = await deps.event_store.load("Plan", plan_id)
    assert events == []
    assert version == 0
