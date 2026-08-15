"""Property-based tests for `record_witnessed_run_outcome.decide` (Run BC).

Complements the example-based `test_record_witnessed_run_outcome_decider.py`
with universal claims across generated inputs. The decider closes a
witnessed Run:

    (state, command, now) -> list[RunCompleted] | list[RunAborted]

Load-bearing properties:

  - A non-Monitor trigger always raises `RunMonitorTriggerNotPermittedError`,
    regardless of every other input (including state=None) -- request-shape
    rejection, checked first, mirrors `record_witnessed_run`'s own PBT.
  - A non-terminal `observed_phase` always raises `RunCapturePhaseNotTerminalError`,
    regardless of state.
  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - A Conducted Run always raises `RunNotWitnessedError` carrying its
    conduct_mode, regardless of status or observed_phase.
  - A future `observed_at` always raises `InvalidRunObservedAtError`.
  - The source-state partition is total over `RunStatus` for a Witnessed
    Run: `Running` emits exactly one event (RunCompleted for Ended,
    RunAborted for Aborted) carrying `observed_at` verbatim; every other
    status raises the matching Cannot*Error carrying the current status.
  - The emitted event's run_id is `state.id`, never `command.run_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.run.aggregates.run import (
    CaptureProgressSnapshot,
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
from tests._strategies import printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime as _datetime

_PLAN_ID = UUID(int=1)
_MONITOR_SOURCE_ID = UUID(int=3)
_CAPTURE_CODE = printable_ascii_text(min_size=1, max_size=64)

_TERMINABLE_SOURCES = (RunStatus.RUNNING,)
_NONTERMINABLE_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_TERMINABLE_SOURCES))
_TERMINAL_PHASES = (CapturePhase.ENDED, CapturePhase.ABORTED)
_NONTERMINAL_PHASES = tuple(p for p in CapturePhase if p not in frozenset(_TERMINAL_PHASES))

_ANY_STATUS = st.sampled_from(list(RunStatus))
_ANY_CONDUCT_MODE = st.sampled_from(list(ConductMode))
_ANY_PHASE = st.sampled_from(list(CapturePhase))
_SOME_NOW = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2200, 1, 1),
    timezones=st.just(UTC),
)
_SOME_COUNT = st.none() | st.floats(
    allow_nan=False, allow_infinity=False, min_value=0, max_value=1e7
)
_SOME_SNAPSHOT = st.none() | st.builds(
    CaptureProgressSnapshot,
    collected_count=_SOME_COUNT,
    collected_total=_SOME_COUNT,
    collected_at=st.none() | _SOME_NOW,
    saved_count=_SOME_COUNT,
    saved_total=_SOME_COUNT,
    saved_at=st.none() | _SOME_NOW,
)


def _run(*, run_id: UUID, status: RunStatus, conduct_mode: ConductMode) -> Run:
    return Run(
        id=run_id,
        name=RunName("2BM fly scan"),
        plan_id=_PLAN_ID,
        subject_id=None,
        status=status,
        conduct_mode=conduct_mode,
    )


def _command(
    *,
    run_id: UUID,
    capture_code: str,
    observed_phase: CapturePhase,
    observed_at: _datetime | None,
    trigger: str,
    capture_progress_snapshot: CaptureProgressSnapshot | None = None,
) -> RecordWitnessedRunOutcome:
    return RecordWitnessedRunOutcome(
        run_id=run_id,
        capture_code=capture_code,
        observed_phase=observed_phase,
        observed_at=observed_at,
        monitor_source_id=_MONITOR_SOURCE_ID,  # type: ignore[arg-type]
        trigger=trigger,
        capture_progress_snapshot=capture_progress_snapshot,
    )


# ---------- Trigger guard: request-shape, unconditional ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=_ANY_PHASE,
    status=_ANY_STATUS,
    conduct_mode=_ANY_CONDUCT_MODE,
    trigger=st.text().filter(lambda t: t != "Monitor"),
    now=_SOME_NOW,
)
def test_non_monitor_trigger_always_raises_regardless_of_everything_else(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    status: RunStatus,
    conduct_mode: ConductMode,
    trigger: str,
    now: _datetime,
) -> None:
    state = _run(run_id=run_id, status=status, conduct_mode=conduct_mode)
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=None,
                trigger=trigger,
            ),
            now=now,
        )


@pytest.mark.unit
@given(run_id=st.uuids(), capture_code=_CAPTURE_CODE, phase=_ANY_PHASE, now=_SOME_NOW)
def test_non_monitor_trigger_raises_even_against_a_nonexistent_run(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    with pytest.raises(RunMonitorTriggerNotPermittedError):
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=None,
                trigger="Operator",
            ),
            now=now,
        )


# ---------- Phase guard: request-shape, checked before state ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=st.sampled_from(_NONTERMINAL_PHASES),
    now=_SOME_NOW,
)
def test_non_terminal_phase_always_raises_even_against_a_nonexistent_run(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    with pytest.raises(RunCapturePhaseNotTerminalError):
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=None,
                trigger="Monitor",
            ),
            now=now,
        )


# ---------- Existence guard ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
)
def test_none_state_always_raises_not_found(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    with pytest.raises(RunNotFoundError) as exc:
        record_witnessed_run_outcome.decide(
            state=None,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=None,
                trigger="Monitor",
            ),
            now=now,
        )
    assert exc.value.run_id == run_id


# ---------- Conduct-mode applicability guard ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    status=_ANY_STATUS,
    phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
)
def test_conducted_run_always_raises_not_witnessed_regardless_of_status_or_phase(
    run_id: UUID,
    capture_code: str,
    status: RunStatus,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    state = _run(run_id=run_id, status=status, conduct_mode=ConductMode.CONDUCTED)
    with pytest.raises(RunNotWitnessedError) as exc:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=None,
                trigger="Monitor",
            ),
            now=now,
        )
    assert exc.value.run_id == run_id
    assert exc.value.conduct_mode == "Conducted"


# ---------- observed_at guard ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
    gap=st.integers(min_value=1, max_value=86_400),
)
def test_future_observed_at_always_raises_invalid(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
    gap: int,
) -> None:
    observed_at = now + timedelta(seconds=gap)
    state = _run(run_id=run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    with pytest.raises(InvalidRunObservedAtError):
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=phase,
                observed_at=observed_at,
                trigger="Monitor",
            ),
            now=now,
        )


# ---------- Source-state partition, for a Witnessed Run ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    observed_at=st.none() | _SOME_NOW,
    now=_SOME_NOW,
)
def test_running_witnessed_ended_emits_single_completed_with_observed_at_threaded(
    run_id: UUID,
    capture_code: str,
    observed_at: _datetime | None,
    now: _datetime,
) -> None:
    assume(observed_at is None or observed_at <= now)
    state = _run(run_id=run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=run_id,
            capture_code=capture_code,
            observed_phase=CapturePhase.ENDED,
            observed_at=observed_at,
            trigger="Monitor",
        ),
        now=now,
    )
    assert events == [RunCompleted(run_id=run_id, occurred_at=now, observed_at=observed_at)]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    observed_at=st.none() | _SOME_NOW,
    now=_SOME_NOW,
)
def test_running_witnessed_aborted_emits_single_aborted_with_observed_at_threaded(
    run_id: UUID,
    capture_code: str,
    observed_at: _datetime | None,
    now: _datetime,
) -> None:
    assume(observed_at is None or observed_at <= now)
    state = _run(run_id=run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=run_id,
            capture_code=capture_code,
            observed_phase=CapturePhase.ABORTED,
            observed_at=observed_at,
            trigger="Monitor",
        ),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RunAborted)
    assert event.run_id == run_id
    assert event.occurred_at == now
    assert event.observed_at == observed_at
    assert capture_code in event.reason


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    observed_phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
    snapshot=_SOME_SNAPSHOT,
)
def test_capture_progress_snapshot_threads_verbatim_onto_either_terminal(
    run_id: UUID,
    capture_code: str,
    observed_phase: CapturePhase,
    now: _datetime,
    snapshot: CaptureProgressSnapshot | None,
) -> None:
    """For any snapshot value (including None), the emitted event's
    `capture_progress_snapshot` is identically the command's, on
    whichever terminal fires. No validation, no substitution."""
    state = _run(run_id=run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=run_id,
            capture_code=capture_code,
            observed_phase=observed_phase,
            observed_at=None,
            trigger="Monitor",
            capture_progress_snapshot=snapshot,
        ),
        now=now,
    )
    assert len(events) == 1
    assert events[0].capture_progress_snapshot == snapshot


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    source=st.sampled_from(_NONTERMINABLE_SOURCES),
    now=_SOME_NOW,
)
def test_nonrunning_witnessed_ended_always_raises_cannot_complete(
    run_id: UUID,
    capture_code: str,
    source: RunStatus,
    now: _datetime,
) -> None:
    state = _run(run_id=run_id, status=source, conduct_mode=ConductMode.WITNESSED)
    with pytest.raises(RunCannotCompleteError) as exc:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=CapturePhase.ENDED,
                observed_at=None,
                trigger="Monitor",
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    source=st.sampled_from(_NONTERMINABLE_SOURCES),
    now=_SOME_NOW,
)
def test_nonrunning_witnessed_aborted_always_raises_cannot_abort(
    run_id: UUID,
    capture_code: str,
    source: RunStatus,
    now: _datetime,
) -> None:
    state = _run(run_id=run_id, status=source, conduct_mode=ConductMode.WITNESSED)
    with pytest.raises(RunCannotAbortError) as exc:
        record_witnessed_run_outcome.decide(
            state=state,
            command=_command(
                run_id=run_id,
                capture_code=capture_code,
                observed_phase=CapturePhase.ABORTED,
                observed_at=None,
                trigger="Monitor",
            ),
            now=now,
        )
    assert exc.value.current_status is source


# ---------- run_id provenance ----------


@pytest.mark.unit
@given(
    state_run_id=st.uuids(),
    command_run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
)
def test_emitted_event_uses_state_id_not_command_run_id(
    state_run_id: UUID,
    command_run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    assume(state_run_id != command_run_id)
    state = _run(run_id=state_run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    events = record_witnessed_run_outcome.decide(
        state=state,
        command=_command(
            run_id=command_run_id,
            capture_code=capture_code,
            observed_phase=phase,
            observed_at=None,
            trigger="Monitor",
        ),
        now=now,
    )
    assert events[0].run_id == state_run_id


# ---------- Purity ----------


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    capture_code=_CAPTURE_CODE,
    phase=st.sampled_from(_TERMINAL_PHASES),
    now=_SOME_NOW,
)
def test_decide_is_pure_same_inputs_same_outputs(
    run_id: UUID,
    capture_code: str,
    phase: CapturePhase,
    now: _datetime,
) -> None:
    state = _run(run_id=run_id, status=RunStatus.RUNNING, conduct_mode=ConductMode.WITNESSED)
    command = _command(
        run_id=run_id,
        capture_code=capture_code,
        observed_phase=phase,
        observed_at=None,
        trigger="Monitor",
    )
    first = record_witnessed_run_outcome.decide(state=state, command=command, now=now)
    second = record_witnessed_run_outcome.decide(state=state, command=command, now=now)
    assert first == second
