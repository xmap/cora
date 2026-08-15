"""Unit tests for the `record_witnessed_run_outcome` slice's pure decider.

Closes a witnessed Run: `Ended` -> `RunCompleted`, `Aborted` ->
`RunAborted`. Mirrors `test_complete_run_decider.py` +
`test_abort_run_decider.py` combined, since one decider produces either
event depending on `command.observed_phase`.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.run.aggregates.run import (
    ConductMode,
    InvalidRunObservedAtError,
    Run,
    RunAborted,
    RunCannotAbortError,
    RunCannotCompleteError,
    RunCapturePhaseNotTerminalError,
    RunCompleted,
    RunMonitorTriggerNotPermittedError,
    RunName,
    RunNotFoundError,
    RunNotWitnessedError,
    RunStatus,
)
from cora.run.features import record_witnessed_run_outcome
from cora.run.features.record_witnessed_run_outcome import RecordWitnessedRunOutcome
from cora.shared.capture_phase import CapturePhase

_NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
_TRIGGER = "Monitor"
_MONITOR_SOURCE_ID = UUID("01900000-0000-7000-8000-000072756e01")


def _run(
    *,
    status: RunStatus = RunStatus.RUNNING,
    conduct_mode: ConductMode = ConductMode.WITNESSED,
) -> Run:
    return Run(
        id=uuid4(),
        name=RunName("2BM fly scan"),
        plan_id=uuid4(),
        subject_id=None,
        status=status,
        conduct_mode=conduct_mode,
    )


def _command(**overrides: object) -> RecordWitnessedRunOutcome:
    defaults: dict[str, object] = {
        "run_id": uuid4(),
        "capture_code": "2bmb-tomoscan",
        "observed_phase": CapturePhase.ENDED,
        "observed_at": _NOW,
        "monitor_source_id": _MONITOR_SOURCE_ID,
        "trigger": _TRIGGER,
    }
    defaults.update(overrides)
    return RecordWitnessedRunOutcome(**defaults)  # type: ignore[arg-type]


# ---------- Ended -> RunCompleted ----------


@pytest.mark.unit
def test_decide_emits_run_completed_for_ended_phase() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(run_id=state.id, observed_phase=CapturePhase.ENDED, observed_at=_NOW),
        now=_NOW,
    )
    assert events == [RunCompleted(run_id=state.id, occurred_at=_NOW, observed_at=_NOW)]


@pytest.mark.unit
def test_decide_carries_none_observed_at_onto_completed_event() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(run_id=state.id, observed_phase=CapturePhase.ENDED, observed_at=None),
        now=_NOW,
    )
    assert events[0].observed_at is None


@pytest.mark.unit
def test_decide_raises_cannot_complete_when_not_running() -> None:
    state = _run(status=RunStatus.COMPLETED)
    with pytest.raises(RunCannotCompleteError) as exc_info:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id, observed_phase=CapturePhase.ENDED),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.COMPLETED


# ---------- Aborted -> RunAborted ----------


@pytest.mark.unit
def test_decide_emits_run_aborted_for_aborted_phase() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=state.id,
            capture_code="2bmb-tomoscan",
            observed_phase=CapturePhase.ABORTED,
            observed_at=_NOW,
        ),
        now=_NOW,
    )
    assert events == [
        RunAborted(
            run_id=state.id,
            reason="RunWitness observed capture 2bmb-tomoscan as Aborted",
            occurred_at=_NOW,
            observed_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_composes_abort_reason_from_capture_code_not_operator_input() -> None:
    """No operator-injectable text reaches RunAborted.reason through this
    command: the command carries no reason field at all."""
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=state.id, capture_code="32id-fastccd", observed_phase=CapturePhase.ABORTED
        ),
        now=_NOW,
    )
    event = events[0]
    assert isinstance(event, RunAborted)
    assert "32id-fastccd" in event.reason


@pytest.mark.unit
def test_decide_carries_none_observed_at_onto_aborted_event() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(run_id=state.id, observed_phase=CapturePhase.ABORTED, observed_at=None),
        now=_NOW,
    )
    assert events[0].observed_at is None


@pytest.mark.unit
def test_decide_raises_cannot_abort_when_not_running() -> None:
    state = _run(status=RunStatus.ABORTED)
    with pytest.raises(RunCannotAbortError) as exc_info:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id, observed_phase=CapturePhase.ABORTED),
            now=_NOW,
        )
    assert exc_info.value.current_status is RunStatus.ABORTED


# ---------- The trigger guard ----------


@pytest.mark.unit
@pytest.mark.parametrize("bad_trigger", ["Operator", "API", "", "monitor"])
def test_decide_rejects_any_non_monitor_trigger(bad_trigger: str) -> None:
    state = _run()
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id, trigger=bad_trigger),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_bad_trigger_before_checking_state() -> None:
    """Request-shape rejection: fires even against a nonexistent Run."""
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(trigger="Operator"),
            now=_NOW,
        )


# ---------- The phase guard ----------


@pytest.mark.unit
@pytest.mark.parametrize(
    "non_terminal_phase", [CapturePhase.BEGUN, CapturePhase.PROGRESSING, CapturePhase.UNRECOGNIZED]
)
def test_decide_rejects_any_non_terminal_phase(non_terminal_phase: CapturePhase) -> None:
    state = _run()
    with pytest.raises(RunCapturePhaseNotTerminalError):
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id, observed_phase=non_terminal_phase),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_non_terminal_phase_before_checking_state() -> None:
    with pytest.raises(RunCapturePhaseNotTerminalError):
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(observed_phase=CapturePhase.BEGUN),
            now=_NOW,
        )


# ---------- Existence + conduct-mode guards ----------


@pytest.mark.unit
def test_decide_raises_run_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(RunNotFoundError) as exc_info:
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(run_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.run_id == target_id


@pytest.mark.unit
def test_decide_raises_not_witnessed_for_a_conducted_run() -> None:
    """The applicability guard: this command must never terminate an
    operator-driven Run, regardless of its status or the observed phase."""
    state = _run(conduct_mode=ConductMode.CONDUCTED)
    with pytest.raises(RunNotWitnessedError) as exc_info:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.run_id == state.id
    assert exc_info.value.conduct_mode == "Conducted"


# ---------- The observed_at guard ----------


@pytest.mark.unit
def test_decide_raises_invalid_observed_at_when_in_the_future() -> None:
    state = _run()
    future = _NOW + timedelta(seconds=1)
    with pytest.raises(InvalidRunObservedAtError):
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(run_id=state.id, observed_at=future),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_allows_observed_at_equal_to_now() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(run_id=state.id, observed_at=_NOW),
        now=_NOW,
    )
    assert events[0].observed_at == _NOW


@pytest.mark.unit
def test_decide_allows_observed_at_none_regardless_of_now() -> None:
    state = _run()
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(run_id=state.id, observed_at=None),
        now=_NOW,
    )
    assert events[0].observed_at is None


# ---------- Purity ----------


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _run()
    command = _command(run_id=state.id)
    first = record_witnessed_run_outcome.decide(state=state, command=command, now=_NOW)
    second = record_witnessed_run_outcome.decide(state=state, command=command, now=_NOW)
    assert first == second
