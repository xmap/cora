"""Property-based tests for `start_run.decide` (Run BC).

Complements the example-based `test_start_run_decider.py` (and its
clearance / supply / enclosure gate siblings) with universal claims
across generated inputs. `start_run` is a heavily-gated cross-aggregate
genesis returning `RunStartEvents`. The full gate matrix is pinned by
the example tests; the PBT asserts the universal claims that hold
across the whole input space:

  - Any non-None state always raises `RunAlreadyExistsError` carrying
    state.id (idempotency-as-error), regardless of context / command.
  - With zero referencing clearances the decider always raises
    `RunRequiresActiveClearanceError`, regardless of command shape.
  - A Deprecated bound Plan always raises `RunBoundPlanDeprecatedError`.
  - On the happy path (no Subject, no Assets, one Active clearance,
    empty supply/family snapshots, empty effective parameters, no
    Campaign) the single `RunStarted` carries the injected ids:
    run_id=new_id, name (trimmed), plan_id=command.plan_id,
    subject_id=None, occurred_at=now; campaign_events is empty.
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
    Run,
    RunAlreadyExistsError,
    RunBoundPlanDeprecatedError,
    RunName,
    RunRequiresActiveClearanceError,
    RunStarted,
    RunStatus,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_NAME = printable_ascii_text(min_size=1, max_size=200)


def _plan(*, status: PlanStatus = PlanStatus.DEFINED) -> Plan:
    return Plan(
        id=UUID(int=10),
        name=PlanName("32-ID FlyScan"),
        practice_id=UUID(int=11),
        asset_ids=frozenset(),
        status=status,
    )


def _active_clearances() -> tuple[ClearanceLookupResult, ...]:
    return (
        ClearanceLookupResult(
            clearance_id=UUID(int=20),
            status="Active",
            template_id=UUID(int=21),
            template_code="ESAF",
            facility_code="aps",
        ),
    )


def _context(
    *,
    plan_status: PlanStatus = PlanStatus.DEFINED,
    clearances: tuple[ClearanceLookupResult, ...] | None = None,
) -> RunStartContext:
    return RunStartContext(
        plan=_plan(status=plan_status),
        subject=None,
        assets={},
        referencing_clearances=_active_clearances() if clearances is None else clearances,
    )


def _command(*, name: str, plan_id: UUID) -> StartRun:
    return StartRun(name=name, plan_id=plan_id, subject_id=None)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(RunStatus)),
    name=_NAME,
    plan_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_start_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: RunStatus,
    name: str,
    plan_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises RunAlreadyExistsError carrying state.id."""
    existing = Run(
        id=existing_id,
        name=RunName("prior"),
        plan_id=UUID(int=1),
        subject_id=None,
        status=existing_status,
    )
    with pytest.raises(RunAlreadyExistsError) as exc:
        start_run.decide(
            state=existing,
            command=_command(name=name, plan_id=plan_id),
            context=_context(),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )
    assert exc.value.run_id == existing_id


@pytest.mark.unit
@given(name=_NAME, plan_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_start_without_referencing_clearance_always_raises_requires_clearance(
    name: str,
    plan_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Zero referencing clearances always raises RunRequiresActiveClearanceError."""
    with pytest.raises(RunRequiresActiveClearanceError):
        start_run.decide(
            state=None,
            command=_command(name=name, plan_id=plan_id),
            context=_context(clearances=()),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(name=_NAME, plan_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_start_with_deprecated_plan_always_raises_plan_deprecated(
    name: str,
    plan_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """A Deprecated bound Plan always raises RunBoundPlanDeprecatedError."""
    with pytest.raises(RunBoundPlanDeprecatedError):
        start_run.decide(
            state=None,
            command=_command(name=name, plan_id=plan_id),
            context=_context(plan_status=PlanStatus.DEPRECATED),
            needed_family_ids_snapshot=frozenset(),
            effective_parameters={},
            method_parameters_schema=None,
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(name=_NAME, plan_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_start_happy_path_emits_single_run_started_with_injected_ids(
    name: str,
    plan_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """The happy path emits one RunStarted with new_id + injected fields, no campaign events."""
    result = start_run.decide(
        state=None,
        command=_command(name=name, plan_id=plan_id),
        context=_context(),
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    assert result.campaign_events == []
    assert len(result.run_events) == 1
    event = result.run_events[0]
    assert isinstance(event, RunStarted)
    assert event.run_id == new_id
    assert event.name == name
    assert event.plan_id == plan_id
    assert event.subject_id is None
    assert event.campaign_id is None
    assert event.occurred_at == now


@pytest.mark.unit
@given(name=_NAME, plan_id=st.uuids(), now=aware_datetimes(), new_id=st.uuids())
def test_start_is_pure_same_input_same_output(
    name: str,
    plan_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    command = _command(name=name, plan_id=plan_id)
    context = _context()
    first = start_run.decide(
        state=None,
        command=command,
        context=context,
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    second = start_run.decide(
        state=None,
        command=command,
        context=context,
        needed_family_ids_snapshot=frozenset(),
        effective_parameters={},
        method_parameters_schema=None,
        now=now,
        new_id=new_id,
    )
    assert first == second
