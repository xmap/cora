"""Property-based tests for `abort_procedure.decide` (Operation BC).

Complements the example-based `test_abort_procedure_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM terminal with a reason

    (state, command, now) -> list[ProcedureAborted]

Load-bearing properties:

  - state=None always raises `ProcedureNotFoundError` carrying
    command.procedure_id.
  - The source-state partition is total over `ProcedureStatus`: each
    source in `{Running, Held}` emits exactly one `ProcedureAborted`
    (procedure_id=state.id, reason threaded, occurred_at=now); every
    other status raises `ProcedureCannotAbortError` carrying the
    current status.
  - The emitted event's procedure_id is `state.id`, never
    command.procedure_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureAborted,
    ProcedureCannotAbortError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import abort_procedure
from cora.operation.features.abort_procedure import AbortProcedure
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)

_ABORTABLE_SOURCES = (ProcedureStatus.RUNNING, ProcedureStatus.HELD)
_DISALLOWED_SOURCES = tuple(s for s in ProcedureStatus if s not in frozenset(_ABORTABLE_SOURCES))


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
def test_abort_with_none_state_always_raises_not_found(
    procedure_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `ProcedureNotFoundError` carrying command id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        abort_procedure.decide(
            state=None,
            command=AbortProcedure(procedure_id=procedure_id, reason=reason),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_ABORTABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abort_from_permitted_source_emits_single_event(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """Running or Held emits one ProcedureAborted with the threaded reason."""
    events = abort_procedure.decide(
        state=_procedure(procedure_id=procedure_id, status=source),
        command=AbortProcedure(procedure_id=procedure_id, reason=reason),
        now=now,
    )
    assert events == [ProcedureAborted(procedure_id=procedure_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abort_from_disallowed_source_always_raises_cannot_abort(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any source outside {Running, Held} raises ProcedureCannotAbortError.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(ProcedureCannotAbortError) as exc:
        abort_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=AbortProcedure(procedure_id=procedure_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_procedure_id=st.uuids(),
    command_procedure_id=st.uuids(),
    source=st.sampled_from(_ABORTABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_abort_uses_state_id_not_command_procedure_id(
    state_procedure_id: UUID,
    command_procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's procedure_id is state.id, not command.procedure_id."""
    assume(state_procedure_id != command_procedure_id)
    events = abort_procedure.decide(
        state=_procedure(procedure_id=state_procedure_id, status=source),
        command=AbortProcedure(procedure_id=command_procedure_id, reason=reason),
        now=now,
    )
    assert events[0].procedure_id == state_procedure_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_abort_is_pure_same_input_same_output(
    procedure_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _procedure(procedure_id=procedure_id, status=ProcedureStatus.RUNNING)
    command = AbortProcedure(procedure_id=procedure_id, reason=reason)
    first = abort_procedure.decide(state=state, command=command, now=now)
    second = abort_procedure.decide(state=state, command=command, now=now)
    assert first == second
