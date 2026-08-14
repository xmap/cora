"""Unit tests for the `record_watched_run` slice's pure decider.

The watched-genesis counterpart to `test_start_run_decider.py`. Pins the
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
from cora.run.features import record_watched_run
from cora.run.features.record_watched_run import RecordWatchedRun, RunWatchedStartContext
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


def _command(**overrides: object) -> RecordWatchedRun:
    defaults: dict[str, object] = {
        "name": "watched capture",
        "plan_id": uuid4(),
        "capture_code": "2bmb-tomoscan",
        "monitor_source_id": UUID("01900000-0000-7000-8000-000063617001"),
        "trigger": _TRIGGER,
    }
    defaults.update(overrides)
    return RecordWatchedRun(**defaults)  # type: ignore[arg-type]


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
def test_decide_emits_run_started_recorded_for_valid_watched_capture() -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    new_id = uuid4()
    decision = record_watched_run.decide(
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
    assert event.conduct_mode is ConductMode.RECORDED
    assert event.safety_envelope_verdict == SafetyEnvelopeVerdict(
        enclosure_permitted=True, beam_available=True
    )
    assert event.trigger_source == "CaptureWatcher:2bmb-tomoscan"
    assert dict(event.external_refs[0]) == {"scheme": "capture-code", "value": "2bmb-tomoscan"}


@pytest.mark.unit
def test_decide_hardcodes_recorded_regardless_of_input() -> None:
    """RecordWatchedRun carries no conduct_mode field for a caller to set;
    the decider always stamps RECORDED."""
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    decision = record_watched_run.decide(
        state=None,
        command=_command(plan_id=plan.id),
        context=context,
        needed_family_ids_snapshot=frozenset({cap}),
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert decision.run_events[0].conduct_mode is ConductMode.RECORDED


# ---------- The trigger guard ----------


@pytest.mark.unit
@pytest.mark.parametrize("bad_trigger", ["Operator", "API", "", "monitor"])
def test_decide_rejects_any_non_monitor_trigger(bad_trigger: str) -> None:
    cap = uuid4()
    asset_id = uuid4()
    plan = _plan(asset_ids=frozenset({asset_id}))
    asset = _asset(asset_id=asset_id, family_ids=frozenset({cap}))
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
        referencing_enclosures=(_enclosure("NotPermitted", "Active"),),
        beam_availability=_beam(quality_ok=False),
    )
    decision = record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=(),
    )
    with pytest.raises(RunRequiresActiveClearanceError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
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
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=_plan(),
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunAlreadyExistsError) as exc:
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunBoundPlanDeprecatedError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=subject,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunSubjectNotMountableError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunPlanAssetDecommissionedError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={asset_id: asset},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(RunCapabilitiesNotSatisfiedError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
    )
    with pytest.raises(InvalidRunNameError):
        record_watched_run.decide(
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
    context = RunWatchedStartContext(
        plan=plan,
        subject=None,
        assets={},
        referencing_clearances=_active_clearance_stub(),
        active_cautions=(caution,),
    )
    decision = record_watched_run.decide(
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
