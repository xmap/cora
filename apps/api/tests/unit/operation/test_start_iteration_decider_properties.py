"""Property-based tests for `start_iteration.decide` (Operation BC).

Universal claims across generated inputs:

  - Running + nothing open + iteration_index == iteration_count + 1
    emits exactly one ProcedureIterationStarted with the injected index
    and now.
  - state=None always raises ProcedureNotFoundError.
  - A non-Running status always raises ProcedureCannotStartIterationError.
  - An already-open iteration always raises
    ProcedureCannotStartIterationError.
  - A non-successor index always raises ProcedureCannotStartIterationError.
  - Pure: same (state, command, now) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotStartIterationError,
    ProcedureIterationStarted,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import start_iteration
from cora.operation.features.start_iteration import StartProcedureIteration
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NON_RUNNING = st.sampled_from(
    [
        ProcedureStatus.DEFINED,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ]
)


def _procedure(
    procedure_id: UUID,
    *,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
    iteration_count: int = 0,
    current_iteration_index: int | None = None,
) -> Procedure:
    return Procedure(
        id=procedure_id,
        name=ProcedureName("X"),
        kind="center_alignment",
        target_asset_ids=frozenset(),
        parent_run_id=None,
        status=status,
        iteration_count=iteration_count,
        current_iteration_index=current_iteration_index,
    )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    iteration_count=st.integers(min_value=0, max_value=500),
    now=aware_datetimes(),
)
def test_start_iteration_emits_single_event_for_strict_successor(
    procedure_id: UUID, iteration_count: int, now: datetime
) -> None:
    state = _procedure(procedure_id, iteration_count=iteration_count, current_iteration_index=None)
    index = iteration_count + 1
    events = start_iteration.decide(
        state=state,
        command=StartProcedureIteration(procedure_id=procedure_id, iteration_index=index),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureIterationStarted)
    assert event.procedure_id == procedure_id
    assert event.iteration_index == index
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    procedure_id=st.uuids(), index=st.integers(min_value=1, max_value=500), now=aware_datetimes()
)
def test_start_iteration_on_none_state_always_raises_not_found(
    procedure_id: UUID, index: int, now: datetime
) -> None:
    with pytest.raises(ProcedureNotFoundError):
        start_iteration.decide(
            state=None,
            command=StartProcedureIteration(procedure_id=procedure_id, iteration_index=index),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    status=_NON_RUNNING,
    iteration_count=st.integers(min_value=0, max_value=100),
    now=aware_datetimes(),
)
def test_start_iteration_on_non_running_always_raises(
    procedure_id: UUID, status: ProcedureStatus, iteration_count: int, now: datetime
) -> None:
    state = _procedure(procedure_id, status=status, iteration_count=iteration_count)
    with pytest.raises(ProcedureCannotStartIterationError):
        start_iteration.decide(
            state=state,
            command=StartProcedureIteration(
                procedure_id=procedure_id, iteration_index=iteration_count + 1
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    open_index=st.integers(min_value=1, max_value=100),
    index=st.integers(min_value=1, max_value=200),
    now=aware_datetimes(),
)
def test_start_iteration_while_open_always_raises(
    procedure_id: UUID, open_index: int, index: int, now: datetime
) -> None:
    state = _procedure(procedure_id, iteration_count=open_index, current_iteration_index=open_index)
    with pytest.raises(ProcedureCannotStartIterationError):
        start_iteration.decide(
            state=state,
            command=StartProcedureIteration(procedure_id=procedure_id, iteration_index=index),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    iteration_count=st.integers(min_value=0, max_value=100),
    index=st.integers(min_value=0, max_value=200),
    now=aware_datetimes(),
)
def test_start_iteration_non_successor_index_always_raises(
    procedure_id: UUID, iteration_count: int, index: int, now: datetime
) -> None:
    # Only iteration_count + 1 is accepted; everything else must raise.
    if index == iteration_count + 1:
        index += 1
    state = _procedure(procedure_id, iteration_count=iteration_count, current_iteration_index=None)
    with pytest.raises(ProcedureCannotStartIterationError):
        start_iteration.decide(
            state=state,
            command=StartProcedureIteration(procedure_id=procedure_id, iteration_index=index),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    iteration_count=st.integers(min_value=0, max_value=100),
    now=aware_datetimes(),
)
def test_start_iteration_is_pure(procedure_id: UUID, iteration_count: int, now: datetime) -> None:
    state = _procedure(procedure_id, iteration_count=iteration_count)
    command = StartProcedureIteration(
        procedure_id=procedure_id, iteration_index=iteration_count + 1
    )
    first = start_iteration.decide(state=state, command=command, now=now)
    second = start_iteration.decide(state=state, command=command, now=now)
    assert first == second
