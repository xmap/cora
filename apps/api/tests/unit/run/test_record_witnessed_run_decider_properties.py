"""Property-based tests for `record_witnessed_run.decide` (Run BC).

Complements the example-based `test_record_witnessed_run_decider.py`.
Universal claims across generated inputs:

  - Any non-None state always raises `RunAlreadyExistsError`.
  - Any trigger other than the literal "Monitor" always raises
    `RunMonitorTriggerNotPermittedError`, regardless of every other
    input.
  - Zero referencing clearances always raises
    `RunRequiresActiveClearanceError` (still a refusal, per the
    roadmap's rule).
  - On the happy path, the single `RunStarted` always carries
    `conduct_mode=WITNESSED` and a non-None `safety_envelope_verdict`.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    CapturePreconditionBypassSnapshot,
    ConductMode,
    Run,
    RunAlreadyExistsError,
    RunClearanceCoverageMismatchError,
    RunMonitorTriggerNotPermittedError,
    RunName,
    RunRequiresActiveClearanceError,
    RunStarted,
    RunStatus,
)
from cora.run.features import record_witnessed_run
from cora.run.features.record_witnessed_run import RecordWitnessedRun, RunWitnessedStartContext
from cora.shared.identity import MonitorSourceId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=200)
_CAPTURE_CODE = printable_ascii_text(min_size=1, max_size=50)
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000063617001"))
_BYPASS_SNAPSHOTS = st.one_of(
    st.none(),
    st.builds(
        CapturePreconditionBypassSnapshot,
        beam_preconditions_bypassed=st.one_of(st.none(), st.booleans()),
        observed_at=st.one_of(st.none(), aware_datetimes()),
    ),
)
"""Every reachable shape of `capture_precondition_bypass_snapshot`: absent
entirely, or present with any combination of the tri-state boolean and an
optionally-absent substrate timestamp (the undecoded-reading and
no-substrate-time cases `CapturePreconditionBypassSnapshot`'s own docstring
calls out as independently nullable)."""


def _plan(*, status: PlanStatus = PlanStatus.DEFINED) -> Plan:
    return Plan(
        id=UUID(int=30),
        name=PlanName("2BM watched capture"),
        practice_id=UUID(int=31),
        asset_ids=frozenset(),
        status=status,
    )


def _active_clearances() -> tuple[ClearanceLookupResult, ...]:
    return (
        ClearanceLookupResult(
            clearance_id=UUID(int=40),
            status="Active",
            template_id=UUID(int=41),
            template_code="ESAF",
            facility_code="aps",
        ),
    )


def _context(
    *,
    plan_status: PlanStatus = PlanStatus.DEFINED,
    clearances: tuple[ClearanceLookupResult, ...] | None = None,
) -> RunWitnessedStartContext:
    return RunWitnessedStartContext(
        plan=_plan(status=plan_status),
        subject=None,
        assets={},
        referencing_clearances=_active_clearances() if clearances is None else clearances,
    )


def _command(
    *,
    name: str,
    plan_id: UUID,
    capture_code: str,
    trigger: str = "Monitor",
    capture_precondition_bypass_snapshot: CapturePreconditionBypassSnapshot | None = None,
) -> RecordWitnessedRun:
    return RecordWitnessedRun(
        name=name,
        plan_id=plan_id,
        capture_code=capture_code,
        monitor_source_id=_MONITOR_SOURCE_ID,
        trigger=trigger,
        capture_precondition_bypass_snapshot=capture_precondition_bypass_snapshot,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(RunStatus)),
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: RunStatus,
    name: str,
    plan_id: UUID,
    capture_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    existing = Run(
        id=existing_id,
        name=RunName("prior"),
        plan_id=UUID(int=1),
        subject_id=None,
        status=existing_status,
    )
    with pytest.raises(RunAlreadyExistsError) as exc:
        record_witnessed_run.decide(
            state=existing,
            command=_command(name=name, plan_id=plan_id, capture_code=capture_code),
            context=_context(),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )
    assert exc.value.run_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    trigger=st.text(min_size=0, max_size=20).filter(lambda t: t != "Monitor"),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_any_non_monitor_trigger_always_raises(
    name: str,
    plan_id: UUID,
    capture_code: str,
    trigger: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """No input shape can make a non-Monitor trigger pass: the laundering
    wall holds regardless of every other field."""
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run.decide(
            state=None,
            command=_command(
                name=name, plan_id=plan_id, capture_code=capture_code, trigger=trigger
            ),
            context=_context(),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_without_referencing_clearance_always_raises_requires_clearance(
    name: str,
    plan_id: UUID,
    capture_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    with pytest.raises(RunRequiresActiveClearanceError):
        record_witnessed_run.decide(
            state=None,
            command=_command(name=name, plan_id=plan_id, capture_code=capture_code),
            context=_context(clearances=()),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    clearance_status=st.text(min_size=1, max_size=20).filter(lambda s: s != "Active"),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_clearance_present_but_never_active_always_raises_coverage_mismatch(
    name: str,
    plan_id: UUID,
    capture_code: str,
    clearance_status: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Whatever non-Active status a referencing clearance carries, the
    witnessed path still refuses -- it never treats a present-but-inactive
    clearance as witnessed."""
    clearances = (
        ClearanceLookupResult(
            clearance_id=UUID(int=50),
            status=clearance_status,
            template_id=UUID(int=51),
            template_code="ESAF",
            facility_code="aps",
        ),
    )
    with pytest.raises(RunClearanceCoverageMismatchError):
        record_witnessed_run.decide(
            state=None,
            command=_command(name=name, plan_id=plan_id, capture_code=capture_code),
            context=_context(clearances=clearances),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_happy_path_always_emits_witnessed_with_a_verdict(
    name: str,
    plan_id: UUID,
    capture_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """The happy path always stamps WITNESSED and a non-None verdict,
    across the whole generated input space -- never CONDUCTED, never a
    bare safety_envelope_verdict=None."""
    result = record_witnessed_run.decide(
        state=None,
        command=_command(name=name, plan_id=plan_id, capture_code=capture_code),
        context=_context(),
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    assert len(result.run_events) == 1
    event = result.run_events[0]
    assert isinstance(event, RunStarted)
    assert event.conduct_mode is ConductMode.WITNESSED
    assert event.safety_envelope_verdict is not None
    assert event.run_id == new_id
    assert event.name == name
    assert event.plan_id == plan_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_witnessed_is_pure_same_input_same_output(
    name: str,
    plan_id: UUID,
    capture_code: str,
    now: datetime,
    new_id: UUID,
) -> None:
    command = _command(name=name, plan_id=plan_id, capture_code=capture_code)
    context = _context()
    first = record_witnessed_run.decide(
        state=None,
        command=command,
        context=context,
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    second = record_witnessed_run.decide(
        state=None,
        command=command,
        context=context,
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    assert first.run_events == second.run_events


@pytest.mark.unit
@given(
    name=_NAME,
    plan_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    now=aware_datetimes(),
    new_id=st.uuids(),
    snapshot=_BYPASS_SNAPSHOTS,
)
def test_witnessed_carries_the_commands_precondition_bypass_snapshot_verbatim(
    name: str,
    plan_id: UUID,
    capture_code: str,
    now: datetime,
    new_id: UUID,
    snapshot: CapturePreconditionBypassSnapshot | None,
) -> None:
    """Pure pass-through across the whole generated shape space (absent,
    decoded True/False, undecoded-with-a-timestamp, decoded-with-no-
    timestamp): the decider neither validates nor transforms this field,
    unlike every field it actually gates on."""
    result = record_witnessed_run.decide(
        state=None,
        command=_command(
            name=name,
            plan_id=plan_id,
            capture_code=capture_code,
            capture_precondition_bypass_snapshot=snapshot,
        ),
        context=_context(),
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    event = result.run_events[0]
    assert isinstance(event, RunStarted)
    assert event.capture_precondition_bypass_snapshot == snapshot
