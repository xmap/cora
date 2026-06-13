"""End-to-end PG integration: Run.start cross-BC clearance gate.

Composes real PG event store + real `PostgresClearanceLookup` + the
full Run.start handler chain. The unit + adapter tests pin each
piece in isolation; this file pins their COMPOSITION (the gate
agent's #1 coverage gap from the 11a gate review).

Three scenarios:
  1. Active Clearance bound to the Subject -> Run.start succeeds.
  2. NO Clearance references the Run scope -> RunRequiresActiveClearanceError.
  3. Defined-only Clearance references the Subject (none Active) ->
     RunClearanceCoverageMismatchError.

The clearance bindings use SubjectBinding (not RunBinding) to decouple
from FixedIdGenerator ordering -- subject_id is the operator-supplied
input the handler doesn't allocate.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

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
from cora.run.aggregates.run import (
    RunClearanceCoverageMismatchError,
    RunRequiresActiveClearanceError,
)
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceLookup, PostgresClearanceTemplateLookup
from cora.safety.aggregates.clearance import AssetBinding, SubjectBinding
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features import (
    activate_clearance,
    activate_clearance_template,
    append_clearance_review_step,
    approve_clearance,
    define_clearance_template,
    register_clearance,
    start_clearance_review,
    submit_clearance,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.activate_clearance_template import ActivateClearanceTemplate
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.submit_clearance import SubmitClearance
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c002")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d6c2")
_ESAF_TEMPLATE_CODE = "ESAF"
_FACILITY_CODE = "cora"


async def _seed_active_esaf_template(db_pool: asyncpg.Pool) -> UUID:
    """Define + Activate an ESAF clearance template in the "cora" facility.
    Returns the deterministic ClearanceTemplate id (uuid5 over
    (facility_code, template_code)). Uses its own throwaway deps so the
    main test's FixedIdGenerator queue isn't consumed by template event
    ids."""
    seeding_deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4(), uuid4()],  # define event + activate event
    )
    template_id = await define_clearance_template.bind(seeding_deps)(
        DefineClearanceTemplate(
            code=_ESAF_TEMPLATE_CODE,
            title="Experiment Safety Assessment Form",
            facility_code=_FACILITY_CODE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await activate_clearance_template.bind(seeding_deps)(
        ActivateClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return template_id


async def _seed_upstream_chain(
    db_pool: asyncpg.Pool,
    *,
    extra_ids: int = 0,
) -> tuple[Kernel, UUID, UUID]:
    """Build the Plan+Practice+Method+Asset+Subject chain a Run requires.
    Returns (deps, plan_id, subject_id) so the test can wire Clearance
    bindings against subject_id.
    """
    plan_id = uuid4()
    subject_id = uuid4()
    # The FixedIdGenerator queue must serve, in order: capability + 2
    # asset events + method + practice + plan + subject (register +
    # mount) + run id + run event + N extra ids for clearance seeding.
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
    deps = replace(
        build_postgres_deps(
            db_pool,
            now=_NOW,
            ids=queue,
            # Use the REAL PostgresClearanceLookup (override the
            # AlwaysCovered default) so the gate fires against the real
            # proj_safety_clearance_summary projection.
            clearance_lookup=PostgresClearanceLookup(db_pool),
        ),
        # Real PostgresClearanceTemplateLookup so register_clearance's
        # template lookup resolves against the seeded template projection
        # row (Slice 9E adds template-id resolution at register time).
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
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
    return deps, plan_id, subject_id


async def _walk_clearance_to_active(deps: Kernel, subject_id: UUID, template_id: UUID) -> UUID:
    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code=_FACILITY_CODE,
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


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_run_start_succeeds_when_active_clearance_covers_subject(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end happy path: real projection lookup returns an Active
    clearance covering the Run's Subject, decider gate passes,
    RunStarted lands."""
    template_id = await _seed_active_esaf_template(db_pool)
    deps, plan_id, subject_id = await _seed_upstream_chain(db_pool, extra_ids=20)
    # Drain safety projections so the template summary row is visible to
    # the PostgresClearanceTemplateLookup used by register_clearance.
    await _drain_safety(db_pool)
    await _walk_clearance_to_active(deps, subject_id, template_id)
    await _drain_safety(db_pool)

    returned_id = await start_run.bind(deps)(
        StartRun(name="Gated run", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id is not None


@pytest.mark.integration
async def test_run_start_raises_requires_active_when_no_clearance(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end sad path #1: no clearance references the Subject,
    decider raises RunRequiresActiveClearanceError."""
    deps, plan_id, subject_id = await _seed_upstream_chain(db_pool)
    # No clearance seeding -- projection table stays empty for this Subject.
    await _drain_safety(db_pool)

    with pytest.raises(RunRequiresActiveClearanceError):
        await start_run.bind(deps)(
            StartRun(name="Run without clearance", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_run_start_raises_coverage_mismatch_when_only_defined(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end sad path #2: a Defined clearance references the
    Subject but isn't Active. Decider raises
    RunClearanceCoverageMismatchError (distinct from Requires)."""
    template_id = await _seed_active_esaf_template(db_pool)
    deps, plan_id, subject_id = await _seed_upstream_chain(db_pool, extra_ids=5)
    # Drain safety projections so the template summary row is visible to
    # the PostgresClearanceTemplateLookup used by register_clearance.
    await _drain_safety(db_pool)
    # Register but don't transition -- clearance stays in Defined.
    await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code=_FACILITY_CODE,
            title="Stays Defined",
            bindings=frozenset({SubjectBinding(subject_id=subject_id)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_safety(db_pool)

    with pytest.raises(RunClearanceCoverageMismatchError) as exc_info:
        await start_run.bind(deps)(
            StartRun(name="Run with inactive clearance", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.referencing_clearance_count == 1


@pytest.mark.integration
async def test_run_start_succeeds_when_clearance_binds_controller_via_controller_id_back_reference(
    db_pool: asyncpg.Pool,
) -> None:
    """Active Clearance with AssetBinding on a stage Asset's controller
    covers a Run targeting only the stage. Pins the start_run handler's
    scope expansion of `plan.asset_ids` via `Asset.controller_id`
    back-references before calling `clearance_lookup.find_referencing_run`.
    Without the expansion, the controller-bound Clearance is invisible at
    Run start (the lookup's `$3 && asset_binding_ids` overlap finds
    nothing because the controller id is not in the Plan's asset_ids) and
    the safety gate raises RunRequiresActiveClearanceError. Symmetric to
    the snapshot-side traversal pinned in
    test_start_run_caution_snapshot_postgres.py
    (test_run_start_snapshots_controller_caution_via_controller_id_back_reference):
    same scope-expansion, different cross-BC lookup port, both load-bearing
    for the controller-as-Asset honesty win shipped in cb50a69de."""
    template_id = await _seed_active_esaf_template(db_pool)
    assert template_id == clearance_template_stream_id(_FACILITY_CODE, _ESAF_TEMPLATE_CODE)
    controller_asset_id = uuid4()
    stage_asset_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    controller_family_id = family_stream_id(FamilyName("MotionController"))
    stage_family_id = family_stream_id(FamilyName("StageUnderTest"))
    # seed_capability_postgres bypasses the id_generator (direct event
    # store append), so no slot for it in the queue. define_family
    # derives its stream id from the name and pops only the event id,
    # so there is no slot for either family stream id.
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
        *[uuid4() for _ in range(20)],  # clearance walk overhead
    ]
    deps = replace(
        build_postgres_deps(
            db_pool,
            now=_NOW,
            ids=queue,
            clearance_lookup=PostgresClearanceLookup(db_pool),
        ),
        clearance_template_lookup=PostgresClearanceTemplateLookup(db_pool),
    )

    # Controller Asset + stage Asset bound via controller_id. The
    # MotionController Family carries empty Affordances per
    # project_controller_as_asset_stage1_design; the empty-Affordances
    # shape is incidental to this test (the controller_id back-reference
    # is the only state under test).
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

    # Standard Method + Practice + Plan + Subject chain. Plan binds the
    # STAGE only; Subject is required to satisfy upstream invariants
    # but the Clearance below is bound to the CONTROLLER, not the
    # Subject, so the gate must find the Clearance via Asset overlap.
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

    # Drain safety projections so the seeded template summary row is
    # visible to PostgresClearanceTemplateLookup before register_clearance.
    await _drain_safety(db_pool)

    # Load-bearing: Active Clearance bound ONLY to the controller (no
    # SubjectBinding). The scope-expansion is the only path that lets
    # this Clearance cover the stage-targeting Run.
    cid = await register_clearance.bind(deps)(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code=_FACILITY_CODE,
            title="Controller firmware lockout",
            bindings=frozenset({AssetBinding(asset_id=controller_asset_id)}),
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
    await _drain_safety(db_pool)

    returned_id = await start_run.bind(deps)(
        StartRun(name="StageRun", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id is not None, (
        "controller-bound Active Clearance must satisfy the safety gate "
        "for a Plan targeting the driven stage; controller_id "
        "back-reference traversal is the fix"
    )
