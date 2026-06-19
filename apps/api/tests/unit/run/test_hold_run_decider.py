"""Unit tests for the `hold_run` slice's pure decider.

Single-source pause transition: `Running -> Held`. Re-holding,
holding from any terminal, holding before Run-start all raise.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    Run,
    RunCannotHoldError,
    RunHeld,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features import hold_run
from cora.run.features.hold_run import HoldRun

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
def test_decide_emits_run_held_for_running_state() -> None:
    state = _run(status=RunStatus.RUNNING)
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id),
        now=_NOW,
    )
    assert events == [RunHeld(run_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        hold_run.decide(
            state=None,
            command=HoldRun(run_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_hold_when_already_held() -> None:
    """Strict-not-idempotent: re-holding raises."""
    state = _run(status=RunStatus.HELD)
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.HELD


@pytest.mark.unit
@pytest.mark.parametrize(
    "terminal",
    [RunStatus.COMPLETED, RunStatus.ABORTED, RunStatus.STOPPED],
)
def test_decide_raises_cannot_hold_from_any_terminal(terminal: RunStatus) -> None:
    state = _run(status=terminal)
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.current_status is terminal


@pytest.mark.unit
def test_decide_error_message_names_required_running_status() -> None:
    state = _run(status=RunStatus.HELD)
    with pytest.raises(RunCannotHoldError) as exc_info:
        hold_run.decide(
            state=state,
            command=HoldRun(run_id=state.id),
            now=_NOW,
        )
    assert "Running" in str(exc_info.value)


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = HoldRun(run_id=state.id)
    first = hold_run.decide(state=state, command=command, now=_NOW)
    second = hold_run.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_defaults_decided_by_decision_id_to_none_when_omitted() -> None:
    """Default for the optional Decision-causation link is None (operator route)."""
    state = _run(status=RunStatus.RUNNING)
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id_through_to_event() -> None:
    """When an agent runtime supplies it, decided_by_decision_id flows verbatim."""
    state = _run(status=RunStatus.RUNNING)
    decision_id = uuid4()
    events = hold_run.decide(
        state=state,
        command=HoldRun(run_id=state.id, decided_by_decision_id=decision_id),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id
