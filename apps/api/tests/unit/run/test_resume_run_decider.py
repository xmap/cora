"""Unit tests for the `resume_run` slice's pure decider.

Single-source resume transition: `Held -> Running`. Resuming from
Running, from any terminal, or before Run-start all raise.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunCannotResumeError,
    RunName,
    RunNotFoundError,
    RunResumed,
    RunStatus,
)
from cora.run.features import resume_run
from cora.run.features.resume_run import ResumeRun

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _run(*, status: RunStatus = RunStatus.HELD) -> Run:
    return Run(
        id=uuid4(),
        name=RunName("32-ID FlyScan"),
        plan_id=uuid4(),
        subject_id=uuid4(),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_run_resumed_for_held_state() -> None:
    state = _run(status=RunStatus.HELD)
    events = resume_run.decide(
        state=state,
        command=ResumeRun(run_id=state.id),
        now=_NOW,
    )
    assert events == [RunResumed(run_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_onto_event() -> None:
    """An autonomous (RunSupervisor) resume links its Decision; the
    decider passes the id straight through to RunResumed."""
    state = _run(status=RunStatus.HELD)
    decision_id = uuid4()
    events = resume_run.decide(
        state=state,
        command=ResumeRun(run_id=state.id, decided_by_decision_id=decision_id),
        now=_NOW,
    )
    assert events == [
        RunResumed(run_id=state.id, decided_by_decision_id=decision_id, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        resume_run.decide(
            state=None,
            command=ResumeRun(run_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_resume_when_already_running() -> None:
    """Strict-not-idempotent: resuming a Running Run raises."""
    state = _run(status=RunStatus.RUNNING)
    with pytest.raises(RunCannotResumeError) as exc_info:
        resume_run.decide(
            state=state,
            command=ResumeRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.RUNNING


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
def test_decide_raises_cannot_resume_from_any_terminal(terminal: RunStatus) -> None:
    state = _run(status=terminal)
    with pytest.raises(RunCannotResumeError) as exc_info:
        resume_run.decide(
            state=state,
            command=ResumeRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is terminal


@pytest.mark.unit
def test_decide_error_message_names_required_held_status() -> None:
    state = _run(status=RunStatus.RUNNING)
    with pytest.raises(RunCannotResumeError) as exc_info:
        resume_run.decide(
            state=state,
            command=ResumeRun(run_id=state.id),
            now=_NOW,
        )
    assert "Held" in str(exc_info.value)


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = ResumeRun(run_id=state.id)
    first = resume_run.decide(state=state, command=command, now=_NOW)
    second = resume_run.decide(state=state, command=command, now=_NOW)
    assert first == second
