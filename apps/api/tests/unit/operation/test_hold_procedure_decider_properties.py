"""Property-based tests for `hold_procedure.decide` (Operation BC).

Complements the example-based `test_hold_procedure_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source pause transition with a reason:

    (state, command, now) -> list[ProcedureHeld]

Load-bearing properties:

  - state=None always raises `ProcedureNotFoundError` carrying
    command.procedure_id.
  - The source-state partition is total over `ProcedureStatus`: the
    sole source `{Running}` emits exactly one `ProcedureHeld`
    (procedure_id=state.id, reason threaded, occurred_at=now); every
    other status raises `ProcedureCannotHoldError` carrying the current
    status. (Adding a new status auto-extends `_DISALLOWED_SOURCES`.)
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
    ProcedureCannotHoldError,
    ProcedureHeld,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import hold_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_REASON = printable_ascii_text(min_size=1, max_size=500)

_HOLDABLE_SOURCES = (ProcedureStatus.RUNNING,)
_DISALLOWED_SOURCES = tuple(s for s in ProcedureStatus if s not in frozenset(_HOLDABLE_SOURCES))


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
def test_hold_with_none_state_always_raises_not_found(
    procedure_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Empty stream always raises `ProcedureNotFoundError` carrying command id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        hold_procedure.decide(
            state=None,
            command=HoldProcedure(procedure_id=procedure_id, reason=reason),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_HOLDABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_hold_from_permitted_source_emits_single_event(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """Running emits one ProcedureHeld with the threaded reason."""
    events = hold_procedure.decide(
        state=_procedure(procedure_id=procedure_id, status=source),
        command=HoldProcedure(procedure_id=procedure_id, reason=reason),
        now=now,
    )
    assert events == [ProcedureHeld(procedure_id=procedure_id, reason=reason, occurred_at=now)]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_hold_from_disallowed_source_always_raises_cannot_hold(
    procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """Any non-Running source raises ProcedureCannotHoldError carrying the status.

    A valid reason is supplied so the source-state guard is what fires
    (reason validation runs first in the decider).
    """
    with pytest.raises(ProcedureCannotHoldError) as exc:
        hold_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=HoldProcedure(procedure_id=procedure_id, reason=reason),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_procedure_id=st.uuids(),
    command_procedure_id=st.uuids(),
    source=st.sampled_from(_HOLDABLE_SOURCES),
    reason=_REASON,
    now=aware_datetimes(),
)
def test_hold_uses_state_id_not_command_procedure_id(
    state_procedure_id: UUID,
    command_procedure_id: UUID,
    source: ProcedureStatus,
    reason: str,
    now: datetime,
) -> None:
    """The emitted event's procedure_id is state.id, not command.procedure_id."""
    assume(state_procedure_id != command_procedure_id)
    events = hold_procedure.decide(
        state=_procedure(procedure_id=state_procedure_id, status=source),
        command=HoldProcedure(procedure_id=command_procedure_id, reason=reason),
        now=now,
    )
    assert events[0].procedure_id == state_procedure_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), reason=_REASON, now=aware_datetimes())
def test_hold_is_pure_same_input_same_output(
    procedure_id: UUID,
    reason: str,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _procedure(procedure_id=procedure_id, status=ProcedureStatus.RUNNING)
    command = HoldProcedure(procedure_id=procedure_id, reason=reason)
    first = hold_procedure.decide(state=state, command=command, now=now)
    second = hold_procedure.decide(state=state, command=command, now=now)
    assert first == second
