"""Property-based tests for `resume_procedure.decide` (Operation BC).

Complements the example-based `test_resume_procedure_decider.py` with
universal claims across generated inputs. The decider is a pure
single-source resume transition carrying a re-establishment boundary:

    (state, command, now) -> list[ProcedureResumed]

Load-bearing properties:

  - state=None always raises `ProcedureNotFoundError` carrying
    command.procedure_id.
  - A negative re_establishment_boundary always raises
    `InvalidProcedureReEstablishmentBoundaryError` (validated before the
    status guard).
  - The source-state partition is total over `ProcedureStatus`: the sole
    source `{Held}` emits exactly one `ProcedureResumed` (procedure_id=
    state.id, boundary threaded, occurred_at=now); every other status
    raises `ProcedureCannotResumeError`. (Adding a new status
    auto-extends `_DISALLOWED_SOURCES`.)
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
    InvalidProcedureReEstablishmentBoundaryError,
    Procedure,
    ProcedureCannotResumeError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureResumed,
    ProcedureStatus,
)
from cora.operation.features import resume_procedure
from cora.operation.features.resume_procedure import ResumeProcedure
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_BOUNDARY = st.integers(min_value=0, max_value=1_000_000)

_RESUMABLE_SOURCES = (ProcedureStatus.HELD,)
_DISALLOWED_SOURCES = tuple(s for s in ProcedureStatus if s not in frozenset(_RESUMABLE_SOURCES))


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
@given(procedure_id=st.uuids(), boundary=_BOUNDARY, now=aware_datetimes())
def test_resume_with_none_state_always_raises_not_found(
    procedure_id: UUID,
    boundary: int,
    now: datetime,
) -> None:
    """Empty stream always raises `ProcedureNotFoundError` carrying command id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        resume_procedure.decide(
            state=None,
            command=ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(list(ProcedureStatus)),
    boundary=st.integers(max_value=-1),
    now=aware_datetimes(),
)
def test_resume_with_negative_boundary_always_raises_invalid(
    procedure_id: UUID,
    source: ProcedureStatus,
    boundary: int,
    now: datetime,
) -> None:
    """A negative boundary raises before the status guard, for any source state."""
    with pytest.raises(InvalidProcedureReEstablishmentBoundaryError):
        resume_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
            now=now,
        )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_RESUMABLE_SOURCES),
    boundary=_BOUNDARY,
    now=aware_datetimes(),
)
def test_resume_from_permitted_source_emits_single_event(
    procedure_id: UUID,
    source: ProcedureStatus,
    boundary: int,
    now: datetime,
) -> None:
    """Held emits one ProcedureResumed with the threaded boundary."""
    events = resume_procedure.decide(
        state=_procedure(procedure_id=procedure_id, status=source),
        command=ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
        now=now,
    )
    assert events == [
        ProcedureResumed(
            procedure_id=procedure_id, re_establishment_boundary=boundary, occurred_at=now
        )
    ]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    boundary=_BOUNDARY,
    now=aware_datetimes(),
)
def test_resume_from_disallowed_source_always_raises_cannot_resume(
    procedure_id: UUID,
    source: ProcedureStatus,
    boundary: int,
    now: datetime,
) -> None:
    """Any non-Held source raises ProcedureCannotResumeError carrying the status.

    A valid (non-negative) boundary is supplied so the source-state guard
    is what fires (boundary validation runs first in the decider).
    """
    with pytest.raises(ProcedureCannotResumeError) as exc:
        resume_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=source),
            command=ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    boundary=_BOUNDARY,
    now=aware_datetimes(),
)
def test_resume_with_parent_run_held_always_raises(
    procedure_id: UUID,
    boundary: int,
    now: datetime,
) -> None:
    """Off-diagonal guard: a Held Procedure whose parent Run is Held always
    raises (the status guard passes, so the parent-Run guard is what fires)."""
    with pytest.raises(ProcedureCannotResumeError) as exc:
        resume_procedure.decide(
            state=_procedure(procedure_id=procedure_id, status=ProcedureStatus.HELD),
            command=ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary),
            parent_run_held=True,
            now=now,
        )
    assert exc.value.parent_run_held is True


@pytest.mark.unit
@given(
    state_procedure_id=st.uuids(),
    command_procedure_id=st.uuids(),
    source=st.sampled_from(_RESUMABLE_SOURCES),
    boundary=_BOUNDARY,
    now=aware_datetimes(),
)
def test_resume_uses_state_id_not_command_procedure_id(
    state_procedure_id: UUID,
    command_procedure_id: UUID,
    source: ProcedureStatus,
    boundary: int,
    now: datetime,
) -> None:
    """The emitted event's procedure_id is state.id, not command.procedure_id."""
    assume(state_procedure_id != command_procedure_id)
    events = resume_procedure.decide(
        state=_procedure(procedure_id=state_procedure_id, status=source),
        command=ResumeProcedure(
            procedure_id=command_procedure_id, re_establishment_boundary=boundary
        ),
        now=now,
    )
    assert events[0].procedure_id == state_procedure_id


@pytest.mark.unit
@given(procedure_id=st.uuids(), boundary=_BOUNDARY, now=aware_datetimes())
def test_resume_is_pure_same_input_same_output(
    procedure_id: UUID,
    boundary: int,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _procedure(procedure_id=procedure_id, status=ProcedureStatus.HELD)
    command = ResumeProcedure(procedure_id=procedure_id, re_establishment_boundary=boundary)
    first = resume_procedure.decide(state=state, command=command, now=now)
    second = resume_procedure.decide(state=state, command=command, now=now)
    assert first == second
