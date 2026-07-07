"""Unit tests for the `abort_run` slice's pure decider.

Single-source emergency-exit terminal: `Running -> Aborted`.
Aborting from Completed | Aborted raises `RunCannotAbortError`
(strict-not-idempotent). `reason` is validated via the
`RunAbortReason` VO.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InvalidRunAbortReasonError,
    Run,
    RunAborted,
    RunCannotAbortError,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features import abort_run
from cora.run.features.abort_run import AbortRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _run(*, status: RunStatus = RunStatus.RUNNING) -> Run:
    return Run(
        id=uuid4(),
        name=RunName("32-ID FlyScan"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_run_aborted_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = abort_run.decide(
        state=state,
        command=AbortRun(
            run_id=state.id,
            reason="detector overheating",
            justification="operator: aborting for test",
        ),
        now=_NOW,
    )
    assert events == [
        RunAborted(
            run_id=state.id,
            reason="detector overheating",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_reason_via_value_object() -> None:
    state = _run()
    events = abort_run.decide(
        state=state,
        command=AbortRun(
            run_id=state.id,
            reason="  beam dump unscheduled  ",
            justification="operator: aborting for test",
        ),
        now=_NOW,
    )
    assert events[0].reason == "beam dump unscheduled"


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        abort_run.decide(
            state=None,
            command=AbortRun(
                run_id=target_id,
                reason="X",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _run()
    with pytest.raises(InvalidRunAbortReasonError):
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="   ",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _run()
    with pytest.raises(InvalidRunAbortReasonError):
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="a" * 501,
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_cannot_abort_when_already_completed() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotAbortError) as exc_info:
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="X",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )
    assert exc_info.value.run_id == state.id
    assert exc_info.value.current_status is RunStatus.COMPLETED


@pytest.mark.unit
def test_decide_raises_cannot_abort_when_already_aborted() -> None:
    """Strict-not-idempotent: re-aborting an Aborted Run raises."""
    state = _run(status=RunStatus.ABORTED)
    with pytest.raises(RunCannotAbortError) as exc_info:
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="X",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.ABORTED


@pytest.mark.unit
def test_decide_raises_cannot_abort_when_already_stopped() -> None:
    """Stopped is terminal — cannot abort from Stopped."""
    state = _run(status=RunStatus.STOPPED)
    with pytest.raises(RunCannotAbortError) as exc_info:
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="X",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.STOPPED


@pytest.mark.unit
def test_decide_error_message_names_required_running_or_held_status() -> None:
    """6f-3 widened the source set to Running | Held."""
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotAbortError) as exc_info:
        abort_run.decide(
            state=state,
            command=AbortRun(
                run_id=state.id,
                reason="X",
                justification="operator: aborting for test",
            ),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Running" in msg
    assert "Held" in msg


# ---------- 6f-3: Held source acceptance ----------


@pytest.mark.unit
def test_decide_accepts_held_source_state_in_6f3() -> None:
    """Emergencies during a hold are real — abort_run accepts Held."""
    state = _run(status=RunStatus.HELD)
    events = abort_run.decide(
        state=state,
        command=AbortRun(
            run_id=state.id,
            reason="emergency during hold",
            justification="operator: aborting for test",
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "emergency during hold"


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = AbortRun(
        run_id=state.id,
        reason="X",
        justification="operator: aborting for test",
    )
    first = abort_run.decide(state=state, command=command, now=_NOW)
    second = abort_run.decide(state=state, command=command, now=_NOW)
    assert first == second


# ---------- Decision→Run linkage ----------


@pytest.mark.unit
def test_decide_defaults_decided_by_decision_id_to_none_when_omitted() -> None:
    """Default for the optional Decision-causation link is None."""
    state = _run(status=RunStatus.RUNNING)
    events = abort_run.decide(
        state=state,
        command=AbortRun(
            run_id=state.id,
            reason="detector overheating",
            justification="operator: aborting for test",
        ),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_through_to_event() -> None:
    """When supplied, decided_by_decision_id flows verbatim into the event."""
    state = _run(status=RunStatus.RUNNING)
    decision_id = uuid4()
    events = abort_run.decide(
        state=state,
        command=AbortRun(
            run_id=state.id,
            reason="agent EquipmentAbortDecision triggered",
            decided_by_decision_id=decision_id,
            justification="operator: aborting for test",
        ),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id
