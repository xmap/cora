"""End-to-end integration test: start_run handler against real Postgres.

The keystone integration test — exercises the full upstream chain
(Family + Asset + Method + Practice + Plan + Subject) plus
Run-start, all against real Postgres. This is the first
integration test that touches FIVE BCs in one transaction (Equipment,
Recipe, Subject, Run, plus the cross-cutting Access via principal_id).

Demonstrates the cross-aggregate-validation pattern (gate-review
Q2 / Q5) at the integration layer: handler pre-loads Plan +
Practice + Method + each Asset + Subject from real event-store
streams, builds RunStartContext, decider validates.
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
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dcc3")


@pytest.mark.integration
async def test_start_run_persists_event_with_full_upstream_chain_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000063aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000063ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000063ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000063ab03")
    method_id = UUID("01900000-0000-7000-8000-00000063ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000063ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000063ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000063ad02")
    site_id = UUID("01900000-0000-7000-8000-00000063ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000063af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000063af02")
    subject_id = UUID("01900000-0000-7000-8000-00000063b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000063b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000063b003")
    run_id = UUID("01900000-0000-7000-8000-00000063b101")
    run_event_id = UUID("01900000-0000-7000-8000-00000063b102")

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
            subject_id,
            subject_register_event_id,
            subject_mount_event_id,
            run_id,
            run_event_id,
        ],
    )

    # Seed full upstream chain.
    await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
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
    await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Now start the Run — pre-loads Plan + Practice + Method + Asset + Subject.
    returned_id = await start_run.bind(deps)(
        StartRun(
            name="32-ID FlyScan morning session",
            plan_id=plan_id,
            subject_id=subject_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == run_id

    # Verify the persisted event.
    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RunStarted"
    assert stored.payload == {
        "run_id": str(run_id),
        "name": "32-ID FlyScan morning session",
        "plan_id": str(plan_id),
        "subject_id": str(subject_id),
        "raid": None,
        # 6g-c additive payload fields default to {} / None when no
        # overrides / no Plan defaults / no trigger_source are supplied.
        "override_parameters": {},
        "effective_parameters": {},
        "trigger_source": None,
        # 11a-c-3 additive payload field for `Identifier`-based clearance
        # coverage. Defaults to [] when omitted; forward-compat via
        # `payload.get("external_refs", [])`.
        "external_refs": [],
        # 11b-c additive payload field for non-blocking CautionLookup at
        # Run.start (operator-acknowledged caution ids surfaced as a
        # banner; empty by default when no cautions covered the Run's
        # targets at start time). Forward-compat via
        # `payload.get("acknowledged_cautions", [])`.
        "acknowledged_cautions": [],
        # 6i-c additive payload field for optional Campaign membership
        # at start time. None when StartRun.campaign_id was not
        # provided; forward-compat via `payload.get("campaign_id")`.
        "campaign_id": None,
        # optional Decision-causation link. None when
        # StartRun.decided_by_decision_id was not provided; forward-compat
        # via `payload.get("decided_by_decision_id")`.
        "decided_by_decision_id": None,
        # pins. Empty tuple by default; forward-compat via
        # `payload.get("pinned_calibration_ids", [])`.
        "pinned_calibration_ids": [],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.event_id == run_event_id
    assert stored.metadata == {"command": "StartRun"}

    # Round-trip via load_run.
    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.RUNNING

    # that omit pinned_calibration_ids get an empty frozenset on the
    # folded state — locks the additive-state forward-compat contract
    # end-to-end (event payload → PG round-trip → load_run fold).
    # Mirror of Data BC's 12c-3 pin on test_register_dataset_handler_postgres.
    assert state.pinned_calibration_ids == frozenset()
