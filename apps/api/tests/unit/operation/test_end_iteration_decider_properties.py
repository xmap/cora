"""Property-based tests for `end_iteration.decide` (Operation BC).

Universal claims across generated inputs:

  - Running + open iteration + matching index emits exactly one
    ProcedureIterationEnded carrying the verdict/reason verbatim and now.
  - state=None always raises ProcedureNotFoundError.
  - A non-Running status always raises ProcedureCannotEndIterationError.
  - No open iteration always raises ProcedureCannotEndIterationError.
  - A mismatched index always raises ProcedureCannotEndIterationError.
  - Pure: same (state, command, now) returns the same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotEndIterationError,
    ProcedureIterationEnded,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import end_iteration
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.shared.text_bounds import REASON_MAX_LENGTH
from tests._strategies import aware_datetimes, printable_ascii_text

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
_CONVERGED = st.one_of(st.none(), st.booleans())
# Non-whitespace-after-trim: the decider trims + rejects whitespace-only.
_REASON = st.one_of(
    st.none(),
    printable_ascii_text(min_size=1, max_size=REASON_MAX_LENGTH).filter(lambda s: s.strip() != ""),
)


def _procedure(
    procedure_id: UUID,
    *,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
    iteration_count: int = 1,
    current_iteration_index: int | None = 1,
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
    open_index=st.integers(min_value=1, max_value=500),
    converged=_CONVERGED,
    reason=_REASON,
    now=aware_datetimes(),
)
def test_end_iteration_emits_single_event_carrying_verdict(
    procedure_id: UUID,
    open_index: int,
    converged: bool | None,
    reason: str | None,
    now: datetime,
) -> None:
    state = _procedure(procedure_id, iteration_count=open_index, current_iteration_index=open_index)
    events = end_iteration.decide(
        state=state,
        command=EndProcedureIteration(
            procedure_id=procedure_id,
            iteration_index=open_index,
            converged=converged,
            reason=reason,
        ),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureIterationEnded)
    assert event.iteration_index == open_index
    assert event.converged == converged
    # The decider trims a present reason (None passes through).
    assert event.reason == (reason.strip() if reason is not None else None)
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    procedure_id=st.uuids(), index=st.integers(min_value=1, max_value=500), now=aware_datetimes()
)
def test_end_iteration_on_none_state_always_raises_not_found(
    procedure_id: UUID, index: int, now: datetime
) -> None:
    with pytest.raises(ProcedureNotFoundError):
        end_iteration.decide(
            state=None,
            command=EndProcedureIteration(
                procedure_id=procedure_id, iteration_index=index, converged=None, reason=None
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    status=_NON_RUNNING,
    open_index=st.integers(min_value=1, max_value=100),
    now=aware_datetimes(),
)
def test_end_iteration_on_non_running_always_raises(
    procedure_id: UUID, status: ProcedureStatus, open_index: int, now: datetime
) -> None:
    state = _procedure(
        procedure_id, status=status, iteration_count=open_index, current_iteration_index=open_index
    )
    with pytest.raises(ProcedureCannotEndIterationError):
        end_iteration.decide(
            state=state,
            command=EndProcedureIteration(
                procedure_id=procedure_id, iteration_index=open_index, converged=None, reason=None
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    iteration_count=st.integers(min_value=0, max_value=100),
    index=st.integers(min_value=1, max_value=200),
    now=aware_datetimes(),
)
def test_end_iteration_with_no_open_iteration_always_raises(
    procedure_id: UUID, iteration_count: int, index: int, now: datetime
) -> None:
    state = _procedure(procedure_id, iteration_count=iteration_count, current_iteration_index=None)
    with pytest.raises(ProcedureCannotEndIterationError):
        end_iteration.decide(
            state=state,
            command=EndProcedureIteration(
                procedure_id=procedure_id, iteration_index=index, converged=None, reason=None
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
def test_end_iteration_index_mismatch_always_raises(
    procedure_id: UUID, open_index: int, index: int, now: datetime
) -> None:
    if index == open_index:
        index += 1
    state = _procedure(procedure_id, iteration_count=open_index, current_iteration_index=open_index)
    with pytest.raises(ProcedureCannotEndIterationError):
        end_iteration.decide(
            state=state,
            command=EndProcedureIteration(
                procedure_id=procedure_id, iteration_index=index, converged=None, reason=None
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    open_index=st.integers(min_value=1, max_value=100),
    now=aware_datetimes(),
)
def test_end_iteration_is_pure(procedure_id: UUID, open_index: int, now: datetime) -> None:
    state = _procedure(procedure_id, iteration_count=open_index, current_iteration_index=open_index)
    command = EndProcedureIteration(
        procedure_id=procedure_id, iteration_index=open_index, converged=True, reason=None
    )
    first = end_iteration.decide(state=state, command=command, now=now)
    second = end_iteration.decide(state=state, command=command, now=now)
    assert first == second
