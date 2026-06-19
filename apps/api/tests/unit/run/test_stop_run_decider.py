"""Unit tests for the `stop_run` slice's pure decider.

Multi-source controlled-exit terminal: `Running | Held -> Stopped`.
Stopping any terminal raises (strict-not-idempotent for Stopped).
`reason` validated via the `RunStopReason` VO.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    InvalidRunStopReasonError,
    Run,
    RunCannotStopError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunStopped,
)
from cora.run.features import stop_run
from cora.run.features.stop_run import StopRun

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
def test_decide_emits_run_stopped_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = stop_run.decide(
        state=state,
        command=StopRun(run_id=state.id, reason="hit time budget cleanly"),
        now=_NOW,
    )
    assert events == [
        RunStopped(
            run_id=state.id,
            reason="hit time budget cleanly",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_accepts_held_source_state() -> None:
    """Multi-source guard: stop_run accepts both Running and Held."""
    state = _run(status=RunStatus.HELD)
    events = stop_run.decide(
        state=state,
        command=StopRun(run_id=state.id, reason="ending early during hold"),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].reason == "ending early during hold"


@pytest.mark.unit
def test_decide_trims_reason_via_value_object() -> None:
    state = _run()
    events = stop_run.decide(
        state=state,
        command=StopRun(run_id=state.id, reason="  scan complete; ending early  "),
        now=_NOW,
    )
    assert events[0].reason == "scan complete; ending early"


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        stop_run.decide(
            state=None,
            command=StopRun(run_id=target_id, reason="X"),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_whitespace_only() -> None:
    state = _run()
    with pytest.raises(InvalidRunStopReasonError):
        stop_run.decide(
            state=state,
            command=StopRun(run_id=state.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_reason_for_too_long() -> None:
    state = _run()
    with pytest.raises(InvalidRunStopReasonError):
        stop_run.decide(
            state=state,
            command=StopRun(run_id=state.id, reason="a" * 501),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
def test_decide_raises_cannot_stop_from_any_terminal(terminal: RunStatus) -> None:
    state = _run(status=terminal)
    with pytest.raises(RunCannotStopError) as exc_info:
        stop_run.decide(
            state=state,
            command=StopRun(run_id=state.id, reason="X"),
            now=_NOW,
        )
    assert exc_info.value.current_status is terminal


@pytest.mark.unit
def test_decide_error_message_names_required_running_or_held_status() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotStopError) as exc_info:
        stop_run.decide(
            state=state,
            command=StopRun(run_id=state.id, reason="X"),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Running" in msg
    assert "Held" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = StopRun(run_id=state.id, reason="X")
    first = stop_run.decide(state=state, command=command, now=_NOW)
    second = stop_run.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_defaults_decided_by_decision_id_to_none_when_omitted() -> None:
    """Default for the optional Decision-causation link is None (operator route)."""
    state = _run(status=RunStatus.RUNNING)
    events = stop_run.decide(
        state=state,
        command=StopRun(run_id=state.id, reason="hit time budget cleanly"),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_through_to_event() -> None:
    """When an agent runtime supplies it, decided_by_decision_id flows verbatim."""
    state = _run(status=RunStatus.RUNNING)
    decision_id = uuid4()
    events = stop_run.decide(
        state=state,
        command=StopRun(
            run_id=state.id,
            reason="agent supervisor early-stop",
            decided_by_decision_id=decision_id,
        ),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id
