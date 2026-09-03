"""Unit tests for the `record_witnessed_run` slice's pure decider.

The witnessed-genesis counterpart to `test_start_run_decider.py`. Pins the
governing rule: CORA-side data faults (deprecated Plan, decommissioned
Asset, capability shortfall, absent Clearance or Supply) stay refusals
here exactly as at a driven start; only the enclosure and beam gates are
witnessed instead of enforced.
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
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    CapturePreconditionBypassSnapshot,
    ConductMode,
    InvalidRunNameError,
    Run,
    RunAlreadyExistsError,
    RunBoundPlanDeprecatedError,
    RunCapabilitiesNotSatisfiedError,
    RunClearanceCoverageMismatchError,
    RunMonitorTriggerNotPermittedError,
    RunName,
    RunPlanAssetDecommissionedError,
    RunRequiresActiveClearanceError,
    RunStatus,
    RunSubjectNotMountableError,
    SafetyEnvelopeVerdict,
)
from cora.run.features import record_witnessed_run
from cora.run.features.record_witnessed_run import RecordWitnessedRun, RunWitnessedStartContext
from cora.shared.identifier import Identifier
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
_TRIGGER = "Monitor"


def _active_clearance_stub() -> tuple[ClearanceLookupResult, ...]:
    return (
        ClearanceLookupResult(
            clearance_id=UUID(int=0),
            status="Active",
            template_id=UUID(int=1),
            template_code="ESAF",
            facility_code="aps",
        ),
    )


def _plan(
    *,
    plan_id: UUID | None = None,
    practice_id: UUID | None = None,
    asset_ids: frozenset[UUID] | None = None,
    status: PlanStatus = PlanStatus.DEFINED,
) -> Plan:
    return Plan(
        id=plan_id or uuid4(),
        name=PlanName("2BM watched capture"),
        practice_id=practice_id or uuid4(),
        asset_ids=asset_ids or frozenset({uuid4()}),
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
        name=AssetName("2bmSP1Camera"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=family_ids if family_ids is not None else frozenset(),
    )


def _subject(
    *,
    subject_id: UUID | None = None,
    status: SubjectStatus = SubjectStatus.MOUNTED,
) -> Subject:
    return Subject(
        id=subject_id or uuid4(),
        name=SubjectName("PorousCeramicSample-A"),
        status=status,
    )


def _command(**overrides: object) -> RecordWitnessedRun:
    defaults: dict[str, object] = {
        "name": "watched capture",
        "plan_id": uuid4(),
        "capture_code": "2bmb-tomoscan",
        "monitor_source_id": UUID("01900000-0000-7000-8000-000063617001"),
        "trigger": _TRIGGER,
    }
    defaults.update(overrides)
    return RecordWitnessedRun(**defaults)  # type: ignore[arg-type]


def _beam(
    *,
    fes_open: bool = True,
    sbs_open: bool = True,
    fes_permit: bool = True,
    quality_ok: bool = True,
) -> BeamAvailabilityLookupResult:
    return BeamAvailabilityLookupResult(
        fes_open=fes_open, sbs_open=sbs_open, fes_permit=fes_permit, quality_ok=quality_ok
    )


def _enclosure(permit_status: str, lifecycle: str) -> EnclosureLookupResult:
    return EnclosureLookupResult(
        enclosure_id=uuid4(),
        name="2-BM-B",
        permit_status=permit_status,
        lifecycle=lifecycle,
        permit_status_changed_at=None,
        source_kind=None,
        source_id=None,
    )


# ---------- Happy path ----------


@pytest.mark.unit
def test_decide_emits_run_started_witnessed_for_a_valid_capture() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    new_id = uuid4()
    decision = record_witnessed_run.decide(
        state=None,
        command=_command(name="watched capture", plan_id=plan.id),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )
    assert len(decision.run_events) == 1
    event = decision.run_events[0]
    assert event.conduct_mode is ConductMode.WITNESSED
    assert event.safety_envelope_verdict == SafetyEnvelopeVerdict(
        enclosure_permitted=True, beam_available=True
    )
    assert event.trigger_source == "RunTranslator:2bmb-tomoscan"
    assert dict(event.external_refs[0]) == {"scheme": "capture-code", "value": "2bmb-tomoscan"}
    # No `capture_precondition_bypass_snapshot` supplied on the command:
    # the emitted genesis carries None, never a fabricated snapshot.
    assert event.capture_precondition_bypass_snapshot is None
    # No `orchestrator_ref` supplied on the command either: exactly one
    # external_refs entry, never a second empty/fabricated one.
    assert len(event.external_refs) == 1


@pytest.mark.unit
def test_decide_appends_orchestrator_ref_as_a_second_external_ref() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    ref = Identifier(scheme="bluesky-run-uid", value="d1a0925b-3e24-461b-896a-3737ba88f39b")
    decision = record_witnessed_run.decide(
        state=None,
        command=_command(plan_id=plan.id, orchestrator_ref=ref),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    event = decision.run_events[0]
    assert len(event.external_refs) == 2
    assert dict(event.external_refs[0]) == {"scheme": "capture-code", "value": "2bmb-tomoscan"}
    assert dict(event.external_refs[1]) == {
        "scheme": "bluesky-run-uid",
        "value": "d1a0925b-3e24-461b-896a-3737ba88f39b",
    }


@pytest.mark.unit
def test_decide_carries_the_commands_precondition_bypass_snapshot_onto_the_event() -> None:
    """`capture_precondition_bypass_snapshot` is a pure pass-through: the
    decider does not validate or transform it, mirroring
    `RecordWitnessedRunOutcome.capture_progress_snapshot`'s own posture."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    snapshot = CapturePreconditionBypassSnapshot(beam_preconditions_bypassed=True, observed_at=_NOW)

    decision = record_witnessed_run.decide(
        state=None,
        command=_command(plan_id=plan.id, capture_precondition_bypass_snapshot=snapshot),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )

    assert decision.run_events[0].capture_precondition_bypass_snapshot == snapshot


@pytest.mark.unit
def test_decide_hardcodes_recorded_regardless_of_input() -> None:
    """RecordWitnessedRun carries no conduct_mode field for a caller to set;
    the decider always stamps WITNESSED."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    decision = record_witnessed_run.decide(
        state=None,
        command=_command(plan_id=plan.id),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert decision.run_events[0].conduct_mode is ConductMode.WITNESSED


# ---------- The trigger guard ----------


@pytest.mark.unit
@pytest.mark.parametrize("bad_trigger", ["Operator", "API", "", "monitor"])
def test_decide_rejects_any_non_monitor_trigger(bad_trigger: str) -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id, trigger=bad_trigger),
            context=context,
            needed_family_ids_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Witnessed, not enforced: enclosure + beam ----------


@pytest.mark.unit
def test_decide_records_failing_enclosure_and_beam_instead_of_raising() -> None:
    """The roadmap's central claim for slice 8: every gate failing still
    writes, and the failures are recorded, not refused."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
        referencing_enclosures=(_enclosure("NotPermitted", "Active"),),
        beam_availability=_beam(quality_ok=False),
    )
    decision = record_witnessed_run.decide(
        state=None,
        command=_command(plan_id=plan.id),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    event = decision.run_events[0]
    assert event.safety_envelope_verdict == SafetyEnvelopeVerdict(
        enclosure_permitted=False, beam_available=False
    )


# ---------- Still refusals: clearance + supply ----------


@pytest.mark.unit
def test_decide_no_clearance_still_raises() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=(),
    )
    with pytest.raises(RunRequiresActiveClearanceError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id),
            context=context,
            needed_family_ids_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_clearance_present_but_inactive_still_raises() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=(
            ClearanceLookupResult(
                clearance_id=uuid4(),
                status="Expired",
                template_id=uuid4(),
                template_code="ESAF",
                facility_code="aps",
            ),
        ),
    )
    with pytest.raises(RunClearanceCoverageMismatchError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id),
            context=context,
            needed_family_ids_snapshot=frozenset({cap}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- CORA-side genesis invariants: still refusals ----------


@pytest.mark.unit
def test_decide_on_existing_state_raises_already_exists() -> None:
    existing = Run(
        id=uuid4(),
        name=RunName("prior"),
        plan_id=uuid4(),
        subject_id=None,
        status=RunStatus.RUNNING,
    )
    context = RunWitnessedStartContext(
        plan=_plan(),
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunAlreadyExistsError) as exc:
        record_witnessed_run.decide(
            state=existing,
            command=_command(),
            context=context,
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc.value.run_id == existing.id


@pytest.mark.unit
def test_decide_deprecated_plan_raises() -> None:
    plan = _plan(status=PlanStatus.DEPRECATED)
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunBoundPlanDeprecatedError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id),
            context=context,
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_subject_not_mountable_raises() -> None:
    plan = _plan()
    subject = _subject(status=SubjectStatus.RECEIVED)
    context = RunWitnessedStartContext(
        plan=plan,
        subject=subject,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunSubjectNotMountableError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id, subject_id=subject.id),
            context=context,
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_decommissioned_asset_raises() -> None:
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.DECOMMISSIONED)
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunPlanAssetDecommissionedError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id),
            context=context,
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_capability_shortfall_raises() -> None:
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset())
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunCapabilitiesNotSatisfiedError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id),
            context=context,
            needed_family_ids_snapshot=frozenset({uuid4()}),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_invalid_name_raises() -> None:
    plan = _plan()
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(InvalidRunNameError):
        record_witnessed_run.decide(
            state=None,
            command=_command(plan_id=plan.id, name="   "),
            context=context,
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )


# ---------- Cautions: non-blocking snapshot ----------


@pytest.mark.unit
def test_decide_embeds_active_cautions_snapshot() -> None:
    from cora.infrastructure.ports.caution_lookup import CautionLookupResult

    plan = _plan()
    caution = CautionLookupResult(
        caution_id=uuid4(),
        target_kind="Asset",
        target_id=uuid4(),
        category="Mechanical",
        severity="Caution",
        text_excerpt="Fragile mount",
        workaround_excerpt="Handle gently",
    )
    context = RunWitnessedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
        active_cautions=(caution,),
    )
    decision = record_witnessed_run.decide(
        state=None,
        command=_command(plan_id=plan.id),
        context=context,
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(decision.run_events[0].acknowledged_cautions) == 1
    assert decision.run_events[0].acknowledged_cautions[0].caution_id == caution.caution_id
