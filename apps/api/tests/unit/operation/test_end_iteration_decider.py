"""Pure-decider tests for the `end_iteration` slice.

Closes the currently-open convergence-loop iteration on a Running
Procedure. Rejects a non-Running status, no open iteration, and an
index that does not match the open one. Passes the convergence verdict
and optional reason through to the event verbatim.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InvalidProcedureIterationEndReasonError,
    Procedure,
    ProcedureCannotEndIterationError,
    ProcedureIterationEnded,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import end_iteration
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.shared.decision_signals import DecisionConfidenceSource

_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _procedure(
    *,
    procedure_id: UUID | None = None,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
    iteration_count: int = 1,
    current_iteration_index: int | None = 1,
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
    )


@pytest.mark.unit
def test_decide_emits_iteration_ended_with_verdict() -> None:
    proc = _procedure()  # iteration 1 open
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id, iteration_index=1, converged=True, reason="within tolerance"
        ),
        now=_NOW,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureIterationEnded)
    assert event.procedure_id == proc.id
    assert event.iteration_index == 1
    assert event.converged is True
    assert event.reason == "within tolerance"
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_passes_steering_provenance_through_to_event() -> None:
    proc = _procedure()  # iteration 1 open
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id,
            iteration_index=1,
            converged=None,
            reason=None,
            advised_stop=False,
            reasoning="acquisition peak",
            confidence=0.8,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=("energy=9.0",),
            model_ref="grid_walk",
        ),
        now=_NOW,
    )
    event = events[0]
    assert isinstance(event, ProcedureIterationEnded)
    assert event.advised_stop is False
    assert event.converged is None
    assert event.reasoning == "acquisition peak"
    assert event.confidence == 0.8
    assert event.confidence_source is DecisionConfidenceSource.SELF_REPORTED
    assert event.alternatives == ("energy=9.0",)
    assert event.model_ref == "grid_walk"


@pytest.mark.unit
def test_decide_leaves_steering_provenance_absent_by_default() -> None:
    proc = _procedure()  # iteration 1 open
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id, iteration_index=1, converged=True, reason="ok"
        ),
        now=_NOW,
    )
    event = events[0]
    assert isinstance(event, ProcedureIterationEnded)
    assert event.advised_stop is None
    assert event.reasoning is None
    assert event.confidence is None
    assert event.confidence_source is None
    assert event.alternatives == ()
    assert event.model_ref is None


@pytest.mark.unit
def test_decide_emits_iteration_ended_when_held() -> None:
    """Resumable conduct: an iteration left open when the conduct was paused
    can still be closed while Held (start_iteration stays Running-only)."""
    proc = _procedure(status=ProcedureStatus.HELD)  # iteration 1 open, paused
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id, iteration_index=1, converged=False, reason=None
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureIterationEnded)
    assert events[0].iteration_index == 1


@pytest.mark.unit
def test_decide_passes_none_verdict_and_none_reason() -> None:
    proc = _procedure()
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id, iteration_index=1, converged=None, reason=None
        ),
        now=_NOW,
    )
    assert events[0].converged is None
    assert events[0].reason is None


@pytest.mark.unit
def test_decide_trims_surrounding_whitespace_in_reason() -> None:
    proc = _procedure()
    events = end_iteration.decide(
        state=proc,
        command=EndProcedureIteration(
            procedure_id=proc.id, iteration_index=1, converged=True, reason="  within tolerance  "
        ),
        now=_NOW,
    )
    assert events[0].reason == "within tolerance"


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureIterationEndReasonError):
        end_iteration.decide(
            state=proc,
            command=EndProcedureIteration(
                procedure_id=proc.id, iteration_index=1, converged=True, reason="   "
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        end_iteration.decide(
            state=None,
            command=EndProcedureIteration(
                procedure_id=pid, iteration_index=1, converged=True, reason=None
            ),
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
    with pytest.raises(ProcedureCannotEndIterationError) as exc:
        end_iteration.decide(
            state=proc,
            command=EndProcedureIteration(
                procedure_id=proc.id, iteration_index=1, converged=True, reason=None
            ),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_rejects_when_no_iteration_open() -> None:
    proc = _procedure(iteration_count=2, current_iteration_index=None)
    with pytest.raises(ProcedureCannotEndIterationError) as exc:
        end_iteration.decide(
            state=proc,
            command=EndProcedureIteration(
                procedure_id=proc.id, iteration_index=2, converged=True, reason=None
            ),
            now=_NOW,
        )
    assert exc.value.current_iteration_index is None


@pytest.mark.unit
@pytest.mark.parametrize("bad_index", [1, 3])
def test_decide_rejects_index_mismatch(bad_index: int) -> None:
    proc = _procedure(iteration_count=2, current_iteration_index=2)  # iteration 2 open
    with pytest.raises(ProcedureCannotEndIterationError) as exc:
        end_iteration.decide(
            state=proc,
            command=EndProcedureIteration(
                procedure_id=proc.id, iteration_index=bad_index, converged=True, reason=None
            ),
            now=_NOW,
        )
    assert exc.value.current_iteration_index == 2


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = EndProcedureIteration(
        procedure_id=proc.id, iteration_index=1, converged=False, reason=None
    )
    first = end_iteration.decide(state=proc, command=cmd, now=_NOW)
    second = end_iteration.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
