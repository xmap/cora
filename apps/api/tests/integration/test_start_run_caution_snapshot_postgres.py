"""End-to-end PG integration: Run.start non-blocking caution snapshot.

Composes real PG event store + real `PostgresCautionLookup` + real
`PostgresClearanceLookup` (the 11a-c-3 gate is still in force) + the
full Run.start handler chain. The unit + adapter tests pin each
piece in isolation; this file pins their COMPOSITION (mirrors the
gate agent's coverage gap pattern used for 11a-c-3).

Three scenarios:
  1. Active Caution attached to the Plan's Asset -> RunStarted lands
     with `acknowledged_cautions` containing the seeded caution.
  2. No cautions seeded -> RunStarted lands with
     `acknowledged_cautions=()` (NON-BLOCKING contract pinned).
  3. Retired caution -> NOT in the snapshot (Active-only filter).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.caution._projections import register_caution_projections
from cora.caution.adapters import PostgresCautionLookup
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
)
from cora.caution.features import register_caution, retire_caution
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.retire_caution import RetireCaution
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunStarted, from_stored
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceLookup
from cora.safety.aggregates.clearance import SubjectBinding
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import (
    activate_clearance,
    append_clearance_review_step,
    approve_clearance,
    register_clearance,
    start_clearance_review,
    submit_clearance,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.submit_clearance import SubmitClearance
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000e001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000e002")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dd05")


async def _seed_upstream_chain(
    db_pool: asyncpg.Pool,
    *,
    extra_ids: int = 0,
) -> tuple[Kernel, UUID, UUID, UUID]:
    """Build the Plan+Practice+Method+Asset+Subject chain a Run requires.
    Returns (deps, plan_id, subject_id, asset_id) so the test can wire
    Clearance bindings + Caution targets against the right ids.
    """
    plan_id = uuid4()
    subject_id = uuid4()
    asset_id = uuid4()
    # define_family now derives its stream id from the name and pops
    # only the event id, so there is no cap_id slot in the queue.
    queue = [
        uuid4(),  # cap_event_id           [0]
        asset_id,  #                        [1]
        uuid4(),  # asset_register_event_id [2]
        uuid4(),  # asset_addcap_event_id   [3]
        uuid4(),  # method_id               [4]
        uuid4(),  # method_event_id         [5]
        uuid4(),  # practice_id             [6]
        uuid4(),  # practice_event_id       [7]
        plan_id,
        uuid4(),  # plan_event_id
        subject_id,
        uuid4(),  # subject_register_event_id
        uuid4(),  # subject_mount_event_id
        uuid4(),  # run_id
        uuid4(),  # run_event_id
        *[uuid4() for _ in range(extra_ids)],
    ]
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=queue,
        clearance_lookup=PostgresClearanceLookup(db_pool),
        caution_lookup=PostgresCautionLookup(db_pool),
    )
    cap_id = family_stream_id(FamilyName("FlyMotion"))

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
            capability_id=_CAPABILITY_ID, name="XRF Fly Scan", needed_family_ids=frozenset({cap_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=queue[4], site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=queue[6],
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
    return deps, plan_id, subject_id, asset_id


async def _walk_clearance_to_active(deps: Kernel, subject_id: UUID) -> UUID:
    """Stand up an Active Safety Clearance covering the Subject so
    the 11a-c-3 gate passes; the snapshot test isn't about Safety."""
    template_uuid = clearance_template_stream_id("cora", "ESAF")
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=template_uuid,
        facility_code="cora",
        code="ESAF",
        status="Active",
        version=1,
    )
    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_uuid),
            facility_code="cora",
            title="Pilot",
            bindings=frozenset({SubjectBinding(subject_id=subject_id)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await submit_clearance.bind(deps)(
        SubmitClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_clearance_review.bind(deps)(
        StartClearanceReview(clearance_id=cid, first_reviewer_role="ESH"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await append_clearance_review_step.bind(deps)(
        AppendClearanceReviewStep(
            clearance_id=cid,
            step_index=0,
            role="ESH",
            actor_id=_PRINCIPAL_ID,
            decision="Approved",
            decided_at=_NOW,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await approve_clearance.bind(deps)(
        ApproveClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_clearance.bind(deps)(
        ActivateClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return cid


async def _seed_active_caution_on_asset(
    deps: Kernel,
    *,
    asset_id: UUID,
    severity: CautionSeverity = CautionSeverity.CAUTION,
    text: str = "hexapod stalls below 0.5 mm/s",
) -> UUID:
    return await register_caution.bind(deps)(
        RegisterCaution(
            target=AssetTarget(asset_id=asset_id),
            category=CautionCategory.WEAR,
            severity=severity,
            text=text,
            workaround="run at 0.6 mm/s",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _drain_all(db_pool: asyncpg.Pool) -> None:
    """Drain both Safety and Caution projections (test seeds touch both)."""
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    register_caution_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _read_run_started(deps: Kernel, run_id: UUID) -> RunStarted:
    """Load the RunStarted event for the given run_id from the event store."""
    events, _version = await deps.event_store.load(stream_type="Run", stream_id=run_id)
    started = next(ev for ev in events if ev.event_type == "RunStarted")
    event = from_stored(started)
    assert isinstance(event, RunStarted)
    return event


@pytest.mark.integration
async def test_run_start_snapshots_active_caution_on_asset(
    db_pool: asyncpg.Pool,
) -> None:
    """Active caution on a Plan-bound Asset surfaces on the RunStarted
    payload as a CautionAcknowledgement."""
    deps, plan_id, subject_id, asset_id = await _seed_upstream_chain(db_pool, extra_ids=20)
    await _walk_clearance_to_active(deps, subject_id)
    caution_id = await _seed_active_caution_on_asset(deps, asset_id=asset_id)
    await _drain_all(db_pool)

    run_id = await start_run.bind(deps)(
        StartRun(name="Run with caution", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    event = await _read_run_started(deps, run_id)
    assert len(event.acknowledged_cautions) == 1
    ack = event.acknowledged_cautions[0]
    assert ack.caution_id == caution_id
    assert ack.target_kind == "Asset"
    assert ack.target_id == asset_id
    assert ack.category == "Wear"
    assert ack.severity == "Caution"
    assert ack.text_excerpt == "hexapod stalls below 0.5 mm/s"
    assert ack.workaround_excerpt == "run at 0.6 mm/s"


@pytest.mark.integration
async def test_run_start_snapshot_is_empty_when_no_cautions_seeded(
    db_pool: asyncpg.Pool,
) -> None:
    """No cautions registered on the Asset -> empty acknowledged_cautions
    tuple. Run still starts (NON-BLOCKING contract pinned end-to-end)."""
    deps, plan_id, subject_id, _asset_id = await _seed_upstream_chain(db_pool, extra_ids=20)
    await _walk_clearance_to_active(deps, subject_id)
    await _drain_all(db_pool)

    run_id = await start_run.bind(deps)(
        StartRun(name="Run without cautions", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    event = await _read_run_started(deps, run_id)
    assert event.acknowledged_cautions == ()


@pytest.mark.integration
async def test_run_start_snapshots_controller_caution_via_controller_id_back_reference(
    db_pool: asyncpg.Pool,
) -> None:
    """Active Caution on a stage Asset's controller surfaces on
    RunStarted even when the Plan targets only the stage. Pins the
    start_run handler's scope expansion of `plan.asset_ids` via
    `Asset.controller_id` back-references before calling
    `caution_lookup.find_active_for_run`. Without expansion, this
    Caution would be silent at Run start (controller is not in the
    Plan's asset_ids; the lookup queries `target_id = ANY(asset_ids)`)
    and the controller-as-Asset honesty win would be lost at the
    operator-facing surface."""
    controller_asset_id = uuid4()
    stage_asset_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    controller_family_id = family_stream_id(FamilyName("MotionController"))
    stage_family_id = family_stream_id(FamilyName("StageUnderTest"))
    # define_family derives its stream id from the name and pops only
    # the event id, so there is no slot for either family stream id.
    queue = [
        uuid4(),  # controller family event   [0]
        controller_asset_id,  #                [1]
        uuid4(),  # controller register event  [2]
        uuid4(),  # controller addfamily event [3]
        uuid4(),  # stage family event         [4]
        stage_asset_id,  #                      [5]
        uuid4(),  # stage register event        [6]
        uuid4(),  # stage addfamily event       [7]
        uuid4(),  # method_id                   [8]
        uuid4(),  # method event                [9]
        uuid4(),  # practice_id                 [10]
        uuid4(),  # practice event              [11]
        plan_id,
        uuid4(),  # plan event
        subject_id,
        uuid4(),  # subject register event
        uuid4(),  # subject mount event
        uuid4(),  # run_id
        uuid4(),  # run event
        *[uuid4() for _ in range(30)],  # caution + clearance walk overhead
    ]
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=queue,
        clearance_lookup=PostgresClearanceLookup(db_pool),
        caution_lookup=PostgresCautionLookup(db_pool),
    )

    # Controller Family + Controller Asset (parent root). Plays the
    # MotionController role from project_controller_as_asset_stage1_design;
    # the Family name does not matter to this test (controller-id
    # traversal is purely an Equipment-state shape, not a Family-name
    # shape) but is named honestly.
    await define_family.bind(deps)(
        DefineFamily(name="MotionController", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="ControllerBox", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=controller_asset_id, family_id=controller_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Stage Family + Stage Asset bound to controller via controller_id.
    # Stage is a root Unit-tier asset to keep parent ceremony minimal;
    # the controller_id is the field under test, not the parent hierarchy.
    await define_family.bind(deps)(
        DefineFamily(name="StageUnderTest", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="StageDrivenByController",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
            controller_id=controller_asset_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=stage_asset_id, family_id=stage_family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Standard Method + Practice + Plan + Subject chain. Plan binds to
    # the STAGE only (not the controller); this is the production-
    # shape pattern where Procedures target the driven stage.
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="StageScan",
            needed_family_ids=frozenset({stage_family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS StageScan", method_id=queue[8], site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="ScanOfStage",
            practice_id=queue[10],
            asset_ids=frozenset({stage_asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_subject.bind(deps)(
        RegisterSubject(name="ScanSubject"),
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

    # Clearance covering the Subject so the 11a-c-3 gate passes.
    await _walk_clearance_to_active(deps, subject_id)

    # The load-bearing seed: a Caution targeting the CONTROLLER, not
    # the stage. Without scope expansion via controller_id, this never
    # surfaces at Run start of a stage-targeting Plan.
    caution_id = await _seed_active_caution_on_asset(
        deps,
        asset_id=controller_asset_id,
        text="controller locks up under sustained load",
    )
    await _drain_all(db_pool)

    run_id = await start_run.bind(deps)(
        StartRun(name="StageRun", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    event = await _read_run_started(deps, run_id)
    assert len(event.acknowledged_cautions) == 1, (
        "controller-side Caution must surface on a Plan targeting the "
        "driven stage; controller_id back-reference traversal is the fix"
    )
    ack = event.acknowledged_cautions[0]
    assert ack.caution_id == caution_id
    assert ack.target_kind == "Asset"
    assert ack.target_id == controller_asset_id
    assert ack.text_excerpt == "controller locks up under sustained load"


@pytest.mark.integration
async def test_run_start_excludes_retired_caution_from_snapshot(
    db_pool: asyncpg.Pool,
) -> None:
    """Retired cautions are filtered out by the projection's
    `status='Active'` clause; the snapshot stays empty even though a
    caution existed for the asset at one point."""
    deps, plan_id, subject_id, asset_id = await _seed_upstream_chain(db_pool, extra_ids=20)
    await _walk_clearance_to_active(deps, subject_id)
    retired_id = await _seed_active_caution_on_asset(deps, asset_id=asset_id)
    await retire_caution.bind(deps)(
        RetireCaution(caution_id=retired_id, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_all(db_pool)

    run_id = await start_run.bind(deps)(
        StartRun(name="Run after caution retired", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    event = await _read_run_started(deps, run_id)
    assert event.acknowledged_cautions == ()
