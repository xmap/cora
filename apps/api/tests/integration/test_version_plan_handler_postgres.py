"""End-to-end integration test: version_plan against real Postgres.

Round-trip: full upstream chain + define + version + load_plan
returns the versioned state with `version` set.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.aggregates.plan import PlanStatus, load_plan
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
    version_plan,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.version_plan import VersionPlan
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d170")


@pytest.mark.integration
async def test_version_plan_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000061aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000061ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000061ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000061ab03")
    method_id = UUID("01900000-0000-7000-8000-00000061ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000061ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000061ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000061ad02")
    site_id = UUID("01900000-0000-7000-8000-00000061ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000061af01")
    plan_defined_event_id = UUID("01900000-0000-7000-8000-00000061af02")
    plan_versioned_event_id = UUID("01900000-0000-7000-8000-00000061af03")

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
            plan_defined_event_id,
            plan_versioned_event_id,
        ],
    )

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
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="XRF Fly Scan",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_plan.bind(deps)(
        VersionPlan(plan_id=plan_id, version_tag="2026-Q3"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Plan", plan_id)
    assert stream_version == 2
    assert [e.event_type for e in events] == ["PlanDefined", "PlanVersioned"]
    versioned = events[1]
    assert versioned.event_id == plan_versioned_event_id
    assert versioned.payload["version_tag"] == "2026-Q3"

    state = await load_plan(deps.event_store, plan_id)
    assert state is not None
    assert state.status is PlanStatus.VERSIONED
    assert state.version == "2026-Q3"
    assert state.practice_id == practice_id
    assert state.asset_ids == frozenset({asset_id})
