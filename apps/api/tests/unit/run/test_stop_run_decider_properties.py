"""Property-based tests for `stop_run.decide` (Run BC).

Complements the example-based `test_stop_run_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM terminal with a reason

    (state, command, now) -> list[RunStopped]

Load-bearing properties:

  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - The source-state partition is total over `RunStatus`: the
    non-terminal sources `{Running, Held}` each emit exactly one
    `RunStopped` (run_id=state.id, reason threaded, occurred_at=now);
    every terminal status raises `RunCannotStopError` carrying the
    current status.
  - The emitted event's run_id is `state.id`, never `command.run_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.run.aggregates.run import (
    Run,
    RunCannotStopError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunStopped,
)
from cora.run.features import stop_run
from cora.run.features.stop_run import StopRun
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PLAN_ID = UUID(int=1)
_SUBJECT_ID = UUID(int=2)
_REASON = printable_ascii_text(min_size=1, max_size=500)

_STOPPABLE_SOURCES = (RunStatus.RUNNING, RunStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_STOPPABLE_SOURCES))


def _run(*, run_id: UUID, status: RunStatus) -> Run:
    return Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        status=status,
    )


@pytest.mark.unit
@given(run_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_stop_with_none_state_always_raises_not_found(
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `RunNotFoundError` carrying command.run_id."""
    with pytest.raises(RunNotFoundError) as exc:
        stop_run.decide(state=None, command=StopRun(run_id=run_id, reason=reason), now=now)
    assert exc.value.run_id == run_id


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_STOPPABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_stop_from_permitted_source_emits_single_event(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: datetime,
) -> None:
    """Running and Held both emit one RunStopped with the threaded reason."""
    events = stop_run.decide(
        state=_run(run_id=run_id, status=source),
        command=StopRun(run_id=run_id, reason=reason),
        now=now,
    )
    assert events == [RunStopped(run_id=run_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_stop_from_terminal_source_always_raises_cannot_stop(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any terminal source raises RunCannotStopError carrying the status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(RunCannotStopError) as exc:
        stop_run.decide(
            state=_run(run_id=run_id, status=source),
            command=StopRun(run_id=run_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_run_id=st.uuids(),
    command_run_id=st.uuids(),
    source=st.sampled_from(_STOPPABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_stop_uses_state_id_not_command_run_id(
    state_run_id: UUID,
    command_run_id: UUID,
    source: RunStatus,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's run_id is state.id, not command.run_id."""
    assume(state_run_id != command_run_id)
    events = stop_run.decide(
        state=_run(run_id=state_run_id, status=source),
        command=StopRun(run_id=command_run_id, reason=reason),
        now=now,
    )
    assert events[0].run_id == state_run_id


@pytest.mark.unit
@given(run_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_stop_is_pure_same_input_same_output(
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _run(run_id=run_id, status=RunStatus.RUNNING)
    command = StopRun(run_id=run_id, reason=reason)
    first = stop_run.decide(state=state, command=command, now=now)
    second = stop_run.decide(state=state, command=command, now=now)
    assert first == second
