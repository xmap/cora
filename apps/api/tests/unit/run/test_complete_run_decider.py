"""Unit tests for the `complete_run` slice's pure decider.

Single-source happy-path terminal: `Running -> Completed`.
Re-completing or completing-from-Aborted raises
`RunCannotCompleteError` (strict-not-idempotent).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunCannotCompleteError,
    RunCompleted,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features import complete_run
from cora.run.features.complete_run import CompleteRun

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
def test_decide_emits_run_completed_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = complete_run.decide(
        state=state,
        command=CompleteRun(run_id=state.id),
        now=_NOW,
    )
    assert events == [RunCompleted(run_id=state.id, occurred_at=_NOW, observed_at=None)]


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        complete_run.decide(
            state=None,
            command=CompleteRun(run_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_complete_when_already_completed() -> None:
    """Strict-not-idempotent: re-completing a Completed Run raises."""
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        complete_run.decide(
            state=state,
            command=CompleteRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.run_id == state.id
    assert exc_info.value.current_status is RunStatus.COMPLETED


@pytest.mark.unit
def test_decide_raises_cannot_complete_from_aborted() -> None:
    """Aborted is terminal — completing from Aborted raises."""
    state = _run(status=RunStatus.ABORTED)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        complete_run.decide(
            state=state,
            command=CompleteRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.ABORTED


@pytest.mark.unit
def test_decide_raises_cannot_complete_from_held() -> None:
    """6f-3 Q1 lock: complete_run stays single-source (Running only).
    Completion claims active achievement; an operator wanting to
    complete a held run must Resume → Complete."""
    state = _run(status=RunStatus.HELD)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        complete_run.decide(
            state=state,
            command=CompleteRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.HELD


@pytest.mark.unit
def test_decide_raises_cannot_complete_from_stopped() -> None:
    """Stopped is terminal — completing from Stopped raises."""
    state = _run(status=RunStatus.STOPPED)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        complete_run.decide(
            state=state,
            command=CompleteRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.STOPPED


@pytest.mark.unit
def test_decide_error_message_names_required_running_status() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        complete_run.decide(
            state=state,
            command=CompleteRun(run_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Running" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = CompleteRun(run_id=state.id)
    first = complete_run.decide(state=state, command=command, now=_NOW)
    second = complete_run.decide(state=state, command=command, now=_NOW)
    assert first == second
