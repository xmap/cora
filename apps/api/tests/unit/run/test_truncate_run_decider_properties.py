"""Property-based tests for `truncate_run.decide` (Run BC).

Complements the example-based `test_truncate_run_decider.py` with
universal claims across generated inputs. The decider is a pure
multi-source FSM terminal with a reason

    (state, command, now) -> list[RunTruncated]

Load-bearing properties:

  - state=None always raises `RunNotFoundError` carrying command.run_id.
  - The source-state partition is total over `RunStatus`: the
    non-terminal sources `{Running, Held}` each emit exactly one
    `RunTruncated` (run_id=state.id, reason threaded, occurred_at=now);
    every other status raises `RunCannotTruncateError` carrying the
    current status.
  - A future `interrupted_at` always raises `InvalidRunInterruptedAtError`.
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
    InvalidRunInterruptedAtError,
    Run,
    RunCannotTruncateError,
    RunName,
    RunNotFoundError,
    RunStatus,
    RunTruncated,
)
from cora.run.features import truncate_run
from cora.run.features.truncate_run import TruncateRun
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime as _datetime

_PLAN_ID = UUID(int=1)
_SUBJECT_ID = UUID(int=2)
_REASON = printable_ascii_text(min_size=1, max_size=500)

_TRUNCATABLE_SOURCES = (RunStatus.RUNNING, RunStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in RunStatus if s not in frozenset(_TRUNCATABLE_SOURCES))


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
def test_truncate_with_none_state_always_raises_not_found(
    run_id: UUID,
    reason: str,
    now: _datetime,
) -> None:
    """Empty stream always raises `RunNotFoundError` carrying command.run_id."""
    with pytest.raises(RunNotFoundError) as exc:
        truncate_run.decide(
            state=None,
            command=TruncateRun(run_id=run_id, reason=reason, interrupted_at=None),
            now=now,
        )
    assert exc.value.run_id == run_id


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_TRUNCATABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_from_permitted_source_emits_single_event(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: _datetime,
) -> None:
    """Running and Held both emit one RunTruncated with the threaded reason."""
    events = truncate_run.decide(
        state=_run(run_id=run_id, status=source),
        command=TruncateRun(run_id=run_id, reason=reason, interrupted_at=None),
        now=now,
    )
    assert events == [
        RunTruncated(run_id=run_id, reason=reason, interrupted_at=None, occurred_at=now)
    ]


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_from_disallowed_source_always_raises_cannot_truncate(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: _datetime,
) -> None:
    """Any disallowed source raises RunCannotTruncateError carrying the status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(RunCannotTruncateError) as exc:
        truncate_run.decide(
            state=_run(run_id=run_id, status=source),
            command=TruncateRun(run_id=run_id, reason=reason, interrupted_at=None),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    source=st.sampled_from(_TRUNCATABLE_SOURCES),
    reason=_REASON,
    now=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2200, 1, 1),
        timezones=st.just(UTC),
    ),
    gap=st.integers(min_value=1, max_value=86_400),
)
def test_truncate_with_future_interrupted_at_always_raises_invalid(
    run_id: UUID,
    source: RunStatus,
    reason: str,
    now: _datetime,
    gap: int,
) -> None:
    """A future `interrupted_at` always raises InvalidRunInterruptedAtError."""
    interrupted_at = now + timedelta(seconds=gap)
    with pytest.raises(InvalidRunInterruptedAtError):
        truncate_run.decide(
            state=_run(run_id=run_id, status=source),
            command=TruncateRun(run_id=run_id, reason=reason, interrupted_at=interrupted_at),
            now=now,
        )


@pytest.mark.unit
@given(
    state_run_id=st.uuids(),
    command_run_id=st.uuids(),
    source=st.sampled_from(_TRUNCATABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_uses_state_id_not_command_run_id(
    state_run_id: UUID,
    command_run_id: UUID,
    source: RunStatus,
    reason: str,
    now: _datetime,
) -> None:
    """The emitted event's run_id is state.id, not command.run_id."""
    assume(state_run_id != command_run_id)
    events = truncate_run.decide(
        state=_run(run_id=state_run_id, status=source),
        command=TruncateRun(run_id=command_run_id, reason=reason, interrupted_at=None),
        now=now,
    )
    assert events[0].run_id == state_run_id


@pytest.mark.unit
@given(run_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_truncate_is_pure_same_input_same_output(
    run_id: UUID,
    reason: str,
    now: _datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _run(run_id=run_id, status=RunStatus.RUNNING)
    command = TruncateRun(run_id=run_id, reason=reason, interrupted_at=None)
    first = truncate_run.decide(state=state, command=command, now=now)
    second = truncate_run.decide(state=state, command=command, now=now)
    assert first == second
