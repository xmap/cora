"""Property-based tests for `abort_run.decide` (Run BC).

Complements the example-based `test_abort_run_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM terminal with a reason

    (state, command, now) -> list[RunAborted]

Load-bearing properties:

  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - The source-state partition is total over `RunStatus`: the
    non-terminal sources `{Running, Held}` each emit exactly one
    `RunAborted` (run_id=state.id, reason threaded, occurred_at=now,
    decided_by_decision_id threaded); every other status raises
    `RunCannotAbortError` carrying the current status.
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
    RunAborted,
    RunCannotAbortError,
    RunName,
    RunNotFoundError,
    RunStatus,
)
from cora.run.features import abort_run
from cora.run.features.abort_run import AbortRun
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

_PLAN_ID = UUID(int=1)
_SUBJECT_ID = UUID(int=2)
_REASON = printable_ascii_text(min_size=1, max_size=500)

_ABORTABLE_SOURCES = (RunStatus.RUNNING, RunStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_ABORTABLE_SOURCES))


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
def test_abort_with_none_state_always_raises_not_found(
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `RunNotFoundError` carrying command.run_id."""
    with pytest.raises(RunNotFoundError) as exc:
        abort_run.decide(state=None, command=AbortRun(run_id=run_id, reason=reason), now=now)
    assert exc.value.run_id == run_id


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_ABORTABLE_SOURCES),
    reason=_REASON,
    decision_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
)
def test_abort_from_permitted_source_emits_single_event(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    decision_id: UUID | None,
    now: datetime,
) -> None:
    """Running and Held both emit one RunAborted with the threaded reason."""
    events = abort_run.decide(
        state=_run(run_id=run_id, status=source),
        command=AbortRun(run_id=run_id, reason=reason, decided_by_decision_id=decision_id),
        now=now,
    )
    assert events == [
        RunAborted(
            run_id=run_id,
            reason=reason,
            decided_by_decision_id=decision_id,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abort_from_terminal_source_always_raises_cannot_abort(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any disallowed source raises RunCannotAbortError carrying the status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(RunCannotAbortError) as exc:
        abort_run.decide(
            state=_run(run_id=run_id, status=source),
            command=AbortRun(run_id=run_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_run_id=st.uuids(),
    command_run_id=st.uuids(),
    source=st.sampled_from(_ABORTABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abort_uses_state_id_not_command_run_id(
    state_run_id: UUID,
    command_run_id: UUID,
    source: RunStatus,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's run_id is state.id, not command.run_id."""
    assume(state_run_id != command_run_id)
    events = abort_run.decide(
        state=_run(run_id=state_run_id, status=source),
        command=AbortRun(run_id=command_run_id, reason=reason),
        now=now,
    )
    assert events[0].run_id == state_run_id


@pytest.mark.unit
@given(run_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_abort_is_pure_same_input_same_output(
    run_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _run(run_id=run_id, status=RunStatus.RUNNING)
    command = AbortRun(run_id=run_id, reason=reason)
    first = abort_run.decide(state=state, command=command, now=now)
    second = abort_run.decide(state=state, command=command, now=now)
    assert first == second
