"""Property-based tests for `truncate_procedure.decide` (Operation BC).

Complements the example-based `test_truncate_procedure_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM terminal with a reason

    (state, command, now) -> list[ProcedureTruncated]

Load-bearing properties:

  - state=None always raises `ProcedureNotFoundError` carrying
    command.procedure_id.
  - The source-state partition is total over `ProcedureStatus`: each
    source in `{Running, Held}` emits exactly one `ProcedureTruncated`
    (procedure_id=state.id, reason threaded, occurred_at=now); every
    other status raises `ProcedureCannotTruncateError` carrying the
    current status.
  - A future `interrupted_at` always raises
    `InvalidProcedureInterruptedAtError`.
  - The emitted event's procedure_id is `state.id`, never
    `command.procedure_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    InvalidProcedureInterruptedAtError,
    Procedure,
    ProcedureCannotTruncateError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureTruncated,
)
from cora.operation.features import truncate_procedure
from cora.operation.features.truncate_procedure import TruncateProcedure
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime as _datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)

_TRUNCATABLE_SOURCES = (ProcedureStatus.RUNNING, ProcedureStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in ProcedureStatus if s not in frozenset(_TRUNCATABLE_SOURCES))


def _procedure(*, procedure_id: UUID, status: ProcedureStatus) -> Procedure:
    return Procedure(
        id=procedure_id,
        name=ProcedureName("X"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=status,
        parent_run_id=None,
    )


@pytest.mark.unit
@given(procedure_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_truncate_with_none_state_always_raises_not_found(
    procedure_id: UUID,
    reason: str,
    now: _datetime,
) -> None:
    """Empty stream always raises `ProcedureNotFoundError` carrying the id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        truncate_procedure.decide(
            state=None,
            command=TruncateProcedure(
                procedure_id=procedure_id, reason=reason, interrupted_at=None
            ),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_TRUNCATABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_from_permitted_source_emits_single_event(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: _datetime,
) -> None:
    """Running or Held emits one ProcedureTruncated with the threaded reason."""
    events = truncate_procedure.decide(
        state=_procedure(procedure_id=procedure_id, status=source),
        command=TruncateProcedure(procedure_id=procedure_id, reason=reason, interrupted_at=None),
        now=now,
    )
    assert events == [
        ProcedureTruncated(
            procedure_id=procedure_id,
            reason=reason,
            interrupted_at=None,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_from_disallowed_source_always_raises_cannot_truncate(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: _datetime,
) -> None:
    """Any disallowed source raises ProcedureCannotTruncateError with status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(ProcedureCannotTruncateError) as exc:
        truncate_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=TruncateProcedure(
                procedure_id=procedure_id, reason=reason, interrupted_at=None
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
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
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: _datetime,
    gap: int,
) -> None:
    """A future `interrupted_at` always raises InvalidProcedureInterruptedAtError."""
    interrupted_at = now + timedelta(seconds=gap)
    with pytest.raises(InvalidProcedureInterruptedAtError):
        truncate_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=TruncateProcedure(
                procedure_id=procedure_id, reason=reason, interrupted_at=interrupted_at
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    state_procedure_id=st.uuids(),
    command_procedure_id=st.uuids(),
    source=st.sampled_from(_TRUNCATABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_truncate_uses_state_id_not_command_procedure_id(
    state_procedure_id: UUID,
    command_procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: _datetime,
) -> None:
    """The emitted event's procedure_id is state.id, not command.procedure_id."""
    assume(state_procedure_id != command_procedure_id)
    events = truncate_procedure.decide(
        state=_procedure(procedure_id=state_procedure_id, status=source),
        command=TruncateProcedure(
            procedure_id=command_procedure_id, reason=reason, interrupted_at=None
        ),
        now=now,
    )
    assert events[0].procedure_id == state_procedure_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_truncate_is_pure_same_input_same_output(
    procedure_id: UUID,
    reason: str,
    now: _datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _procedure(procedure_id=procedure_id, status=ProcedureStatus.RUNNING)
    command = TruncateProcedure(procedure_id=procedure_id, reason=reason, interrupted_at=None)
    first = truncate_procedure.decide(state=state, command=command, now=now)
    second = truncate_procedure.decide(state=state, command=command, now=now)
    assert first == second
