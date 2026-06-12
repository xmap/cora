"""Property-based tests for `resume_run.decide` (Run BC).

Complements the example-based `test_resume_run_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM transition

    (state, command, now) -> list[RunResumed]

Load-bearing properties:

  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - The source-state partition is total over `RunStatus`: only
    `Held` emits exactly one `RunResumed` (run_id=state.id,
    occurred_at=now); every other status raises `RunCannotResumeError`
    carrying the current status, so a future status value cannot
    silently fall through.
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
    RunCannotResumeError,
    RunName,
    RunNotFoundError,
    RunResumed,
    RunStatus,
)
from cora.run.features import resume_run
from cora.run.features.resume_run import ResumeRun
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_PLAN_ID = UUID(int=1)
_SUBJECT_ID = UUID(int=2)

_PERMITTED_SOURCES = (RunStatus.HELD,)
_DISALLOWED_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_PERMITTED_SOURCES))


def _run(*, run_id: UUID, status: RunStatus) -> Run:
    return Run(
        id=run_id,
        name=RunName("32-ID FlyScan"),
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        status=status,
    )


@pytest.mark.unit
@given(run_id=st.uuids(), now=aware_datetimes())
def test_resume_with_none_state_always_raises_not_found(
    run_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `RunNotFoundError` carrying command.run_id."""
    with pytest.raises(RunNotFoundError) as exc:
        resume_run.decide(state=None, command=ResumeRun(run_id=run_id), now=now)
    assert exc.value.run_id == run_id


@pytest.mark.unit
@given(run_id=st.uuids(), now=aware_datetimes())
def test_resume_from_held_emits_single_event(run_id: UUID, now: datetime) -> None:
    """Held is the only resumable source; emits one RunResumed."""
    events = resume_run.decide(
        state=_run(run_id=run_id, status=RunStatus.HELD),
        command=ResumeRun(run_id=run_id),
        now=now,
    )
    assert events == [RunResumed(run_id=run_id, occurred_at=now)]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_resume_from_disallowed_source_always_raises_cannot_resume(
    run_id: UUID,
    source: RunStatus,
    now: datetime,
) -> None:
    """Any source other than Held raises, carrying the current status."""
    with pytest.raises(RunCannotResumeError) as exc:
        resume_run.decide(
            state=_run(run_id=run_id, status=source),
            command=ResumeRun(run_id=run_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_run_id=st.uuids(), command_run_id=st.uuids(), now=aware_datetimes())
def test_resume_uses_state_id_not_command_run_id(
    state_run_id: UUID,
    command_run_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's run_id is state.id, not command.run_id."""
    assume(state_run_id != command_run_id)
    events = resume_run.decide(
        state=_run(run_id=state_run_id, status=RunStatus.HELD),
        command=ResumeRun(run_id=command_run_id),
        now=now,
    )
    assert events[0].run_id == state_run_id


@pytest.mark.unit
@given(run_id=st.uuids(), now=aware_datetimes())
def test_resume_is_pure_same_input_same_output(run_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _run(run_id=run_id, status=RunStatus.HELD)
    command = ResumeRun(run_id=run_id)
    first = resume_run.decide(state=state, command=command, now=now)
    second = resume_run.decide(state=state, command=command, now=now)
    assert first == second
