"""Pure-decider tests for the `start_iteration` slice.

Begins one convergence-loop iteration on a Running Procedure. Rejects
a non-Running status, an already-open iteration, and a non-sequential
operator-supplied index. Iteration is orthogonal to the lifecycle FSM
so the emitted event carries no status.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotStartIterationError,
    ProcedureIterationLimitReachedError,
    ProcedureIterationStarted,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import start_iteration
from cora.operation.features.start_iteration import StartProcedureIteration

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _procedure(
    *,
    procedure_id: UUID | None = None,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
    iteration_count: int = 0,
    current_iteration_index: int | None = None,
    consecutive_unconverged_iterations: int = 0,
    max_consecutive_unconverged_iterations: int | None = None,
) -> Procedure:
    return Procedure(
        id=procedure_id or uuid4(),
        name=ProcedureName("X"),
        kind="center_alignment",
        target_asset_ids=frozenset(),
        status=status,
        parent_run_id=None,
        iteration_count=iteration_count,
        current_iteration_index=current_iteration_index,
        consecutive_unconverged_iterations=consecutive_unconverged_iterations,
        max_consecutive_unconverged_iterations=max_consecutive_unconverged_iterations,
    )


@pytest.mark.unit
def test_decide_emits_iteration_started_for_first_iteration() -> None:
    proc = _procedure()  # count=0, nothing open -> next is 1
    events = start_iteration.decide(
        state=proc,
        command=StartProcedureIteration(procedure_id=proc.id, iteration_index=1),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureIterationStarted)
    assert event.procedure_id == proc.id
    assert event.iteration_index == 1
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_emits_next_iteration_after_prior_closed() -> None:
    proc = _procedure(iteration_count=2, current_iteration_index=None)
    events = start_iteration.decide(
        state=proc,
        command=StartProcedureIteration(procedure_id=proc.id, iteration_index=3),
        now=_NOW,
    )
    assert events[0].iteration_index == 3


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        start_iteration.decide(
            state=None,
            command=StartProcedureIteration(procedure_id=pid, iteration_index=1),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ProcedureStatus.DEFINED,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ],
)
def test_decide_rejects_non_running_status(status: ProcedureStatus) -> None:
    proc = _procedure(status=status)
    with pytest.raises(ProcedureCannotStartIterationError) as exc:
        start_iteration.decide(
            state=proc,
            command=StartProcedureIteration(procedure_id=proc.id, iteration_index=1),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_rejects_when_an_iteration_is_already_open() -> None:
    proc = _procedure(iteration_count=1, current_iteration_index=1)
    with pytest.raises(ProcedureCannotStartIterationError) as exc:
        start_iteration.decide(
            state=proc,
            command=StartProcedureIteration(procedure_id=proc.id, iteration_index=2),
            now=_NOW,
        )
    assert exc.value.current_iteration_index == 1


@pytest.mark.unit
@pytest.mark.parametrize("bad_index", [0, 1, 3, 5])
def test_decide_rejects_non_sequential_index(bad_index: int) -> None:
    # count=1, nothing open -> the only accepted index is 2.
    proc = _procedure(iteration_count=1, current_iteration_index=None)
    with pytest.raises(ProcedureCannotStartIterationError) as exc:
        start_iteration.decide(
            state=proc,
            command=StartProcedureIteration(procedure_id=proc.id, iteration_index=bad_index),
            now=_NOW,
        )
    assert exc.value.expected_iteration_index == 2


@pytest.mark.unit
def test_decide_rejects_when_patience_cap_reached() -> None:
    # cap=2, streak=2, otherwise-valid next index -> limit reached.
    proc = _procedure(
        iteration_count=2,
        current_iteration_index=None,
        consecutive_unconverged_iterations=2,
        max_consecutive_unconverged_iterations=2,
    )
    with pytest.raises(ProcedureIterationLimitReachedError) as exc:
        start_iteration.decide(
            state=proc,
            command=StartProcedureIteration(procedure_id=proc.id, iteration_index=3),
            now=_NOW,
        )
    assert exc.value.consecutive_unconverged_iterations == 2
    assert exc.value.max_consecutive_unconverged_iterations == 2


@pytest.mark.unit
def test_decide_allows_iteration_below_patience_cap() -> None:
    # cap=3, streak=2 -> still under budget; emits.
    proc = _procedure(
        iteration_count=2,
        current_iteration_index=None,
        consecutive_unconverged_iterations=2,
        max_consecutive_unconverged_iterations=3,
    )
    events = start_iteration.decide(
        state=proc,
        command=StartProcedureIteration(procedure_id=proc.id, iteration_index=3),
        now=_NOW,
    )
    assert events[0].iteration_index == 3


@pytest.mark.unit
def test_decide_no_cap_never_limits() -> None:
    # No cap (None): a large streak does not block.
    proc = _procedure(
        iteration_count=9,
        current_iteration_index=None,
        consecutive_unconverged_iterations=9,
        max_consecutive_unconverged_iterations=None,
    )
    events = start_iteration.decide(
        state=proc,
        command=StartProcedureIteration(procedure_id=proc.id, iteration_index=10),
        now=_NOW,
    )
    assert events[0].iteration_index == 10


@pytest.mark.unit
def test_decide_sequencing_guard_takes_precedence_over_cap() -> None:
    # Non-Running with streak at cap: the sequencing guard fires first, not
    # the limit error (a malformed request is not a budget outcome).
    proc = _procedure(
        status=ProcedureStatus.DEFINED,
        consecutive_unconverged_iterations=2,
        max_consecutive_unconverged_iterations=2,
    )
    with pytest.raises(ProcedureCannotStartIterationError):
        start_iteration.decide(
            state=proc,
            command=StartProcedureIteration(procedure_id=proc.id, iteration_index=1),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = StartProcedureIteration(procedure_id=proc.id, iteration_index=1)
    first = start_iteration.decide(state=proc, command=cmd, now=_NOW)
    second = start_iteration.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
