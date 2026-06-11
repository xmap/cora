"""End-to-end PG integration test: the full Capability-bound pilot lane.

Walks the complete cross-BC chain in one test:

    define_capability        (Recipe)
        -> define_family     (Equipment)
        -> register_asset    (Equipment)
        -> add_asset_family  (Equipment)
        -> define_method     (Recipe, bound to the Capability)
        -> define_practice   (Recipe)
        -> define_plan       (Recipe, affordance-cover guard passes)
        -> register_procedure (Operation, bound to the SAME Capability)

The existing `test_define_plan_affordance_cover_guard_against_postgres`
covers the failure path of the same chain (Family missing an
affordance). This test pins the happy path AND that the SAME
Capability template can simultaneously bind a Method-shaped executor
(via Method.capability_id at Plan-bind) and a Procedure-shaped
executor (via Procedure.capability_id at register_procedure) when
its `executor_shapes` declares both.

Watch item from the Capability final-coverage gate review (P0):
no single integration test previously walked the full Capability-
bound lane end-to-end through real Postgres. Pinning it here
locks the cross-BC story in.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import Affordance
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.operation.features import register_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.plan import PlanStatus, load_plan
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
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_capability_bound_full_lane_postgres(db_pool: asyncpg.Pool) -> None:
    """Full Capability-bound pilot lane: define_capability → family →
    asset → method → practice → plan → procedure, all against real PG.

    The Capability declares BOTH Method and Procedure executor shapes
    so the same template binds both kinds of executor — Method via
    Plan-bind, Procedure via register_procedure. Affordance cover
    succeeds: Family declares ROTATABLE, Capability requires ROTATABLE."""
    cap_id = UUID("01900000-0000-7000-8000-00000071c001")
    cap_event = UUID("01900000-0000-7000-8000-00000071c002")
    family_id = UUID("01900000-0000-7000-8000-00000071f001")
    family_event = UUID("01900000-0000-7000-8000-00000071f002")
    asset_id = UUID("01900000-0000-7000-8000-00000071a001")
    asset_register_event = UUID("01900000-0000-7000-8000-00000071a002")
    asset_addfam_event = UUID("01900000-0000-7000-8000-00000071a003")
    method_id = UUID("01900000-0000-7000-8000-00000071b001")
    method_event = UUID("01900000-0000-7000-8000-00000071b002")
    practice_id = UUID("01900000-0000-7000-8000-00000071d001")
    practice_event = UUID("01900000-0000-7000-8000-00000071d002")
    site_id = UUID("01900000-0000-7000-8000-00000071e001")
    plan_id = UUID("01900000-0000-7000-8000-00000071e101")
    plan_event = UUID("01900000-0000-7000-8000-00000071e102")
    procedure_id = UUID("01900000-0000-7000-8000-00000071e201")
    procedure_event = UUID("01900000-0000-7000-8000-00000071e202")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            cap_id,
            cap_event,
            family_id,
            family_event,
            asset_id,
            asset_register_event,
            asset_addfam_event,
            method_id,
            method_event,
            practice_id,
            practice_event,
            plan_id,
            plan_event,
            procedure_id,
            procedure_event,
        ],
    )

    # 1. Capability template — declares BOTH executor shapes so the
    #    same template can bind a Method AND a Procedure.
    await define_capability.bind(deps)(
        DefineCapability(
            code="cora.capability.end_to_end",
            name="EndToEnd",
            required_affordances=frozenset({Affordance.ROTATABLE}),
            executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # 2. Family covers the Capability's required ROTATABLE affordance.
    await define_family.bind(deps)(
        DefineFamily(name="RotaryStage", affordances=frozenset({Affordance.ROTATABLE})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # 3. Asset registered + bound to the Family.
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
    # 4. Method bound to the Capability (Method-shaped executor).
    await define_method.bind(deps)(
        DefineMethod(
            name="EndToEndMethod",
            capability_id=cap_id,
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # 5. Practice wraps the Method.
    await define_practice.bind(deps)(
        DefinePractice(name="EndToEndPractice", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # 6. Plan binds the Practice + Asset — 6l.B affordance-cover guard
    #    succeeds because Family.affordances ⊇ Capability.required_affordances.
    returned_plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="EndToEndPlan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_plan_id == plan_id
    # 7. Procedure also binds to the SAME Capability (Procedure-shaped
    #    executor). The 10d executor-shape guard passes because the
    #    Capability declares both METHOD and PROCEDURE shapes.
    returned_procedure_id = await register_procedure.bind(deps)(
        RegisterProcedure(
            name="EndToEndProcedure",
            kind="alignment",
            capability_id=cap_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_procedure_id == procedure_id

    # Round-trip the Plan + Procedure through load_* to confirm the
    # capability_id linkage survives jsonb persistence.
    plan = await load_plan(deps.event_store, plan_id)
    assert plan is not None
    assert plan.status is PlanStatus.DEFINED

    procedure_events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 1
    assert procedure_events[0].payload["capability_id"] == str(cap_id)
