"""Property-based tests for `complete_procedure.decide` (Operation BC).

Complements the example-based `test_complete_procedure_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source FSM terminal

    (state, command, now) -> list[ProcedureCompleted]

Load-bearing properties:

  - state=None always raises `ProcedureNotFoundError` carrying
    command.procedure_id.
  - The source-state partition is total over `ProcedureStatus`: only
    `Running` emits exactly one `ProcedureCompleted` (procedure_id=
    state.id, occurred_at=now); every other status raises
    `ProcedureCannotCompleteError` carrying the current status, so a
    future status value cannot silently fall through.
  - The emitted event's procedure_id is `state.id`, never
    `command.procedure_id`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotCompleteError,
    ProcedureCompleted,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import complete_procedure
from cora.operation.features.complete_procedure import CompleteProcedure
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_COMPLETABLE_SOURCES = (ProcedureStatus.RUNNING,)
_DISALLOWED_SOURCES = tuple(s for s in ProcedureStatus if s not in frozenset(_COMPLETABLE_SOURCES))


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
@given(procedure_id=st.uuids(), now=aware_datetimes())
def test_complete_with_none_state_always_raises_not_found(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ProcedureNotFoundError` carrying command id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        complete_procedure.decide(
            state=None,
            command=CompleteProcedure(procedure_id=procedure_id),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), now=aware_datetimes())
def test_complete_from_running_emits_single_event(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """Running is the only completable source; emits one ProcedureCompleted."""
    events = complete_procedure.decide(
        state=_procedure(procedure_id=procedure_id, status=ProcedureStatus.RUNNING),
        command=CompleteProcedure(procedure_id=procedure_id),
        now=now,
    )
    assert events == [ProcedureCompleted(procedure_id=procedure_id, occurred_at=now)]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_complete_from_disallowed_source_always_raises_cannot_complete(
    procedure_id: UUID,
    source: ProcedureStatus,
    now: datetime,
) -> None:
    """Any source other than Running raises, carrying the current status."""
    with pytest.raises(ProcedureCannotCompleteError) as exc:
        complete_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=CompleteProcedure(procedure_id=procedure_id),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(state_id=st.uuids(), command_id=st.uuids(), now=aware_datetimes())
def test_complete_uses_state_id_not_command_id(
    state_id: UUID,
    command_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's procedure_id is state.id, not command.procedure_id."""
    assume(state_id != command_id)
    events = complete_procedure.decide(
        state=_procedure(procedure_id=state_id, status=ProcedureStatus.RUNNING),
        command=CompleteProcedure(procedure_id=command_id),
        now=now,
    )
    assert events[0].procedure_id == state_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), now=aware_datetimes())
def test_complete_is_pure_same_input_same_output(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _procedure(procedure_id=procedure_id, status=ProcedureStatus.RUNNING)
    command = CompleteProcedure(procedure_id=procedure_id)
    first = complete_procedure.decide(state=state, command=command, now=now)
    second = complete_procedure.decide(state=state, command=command, now=now)
    assert first == second
