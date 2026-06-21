"""Pure-decider tests for `resume_procedure` slice.

Single-source resume transition: `Held -> Running`. Carries
`re_establishment_boundary` (>= 0). Mirrors `resume_run`. The
off-diagonal guard (refuse while the parent Run is Held) lives in the
decider via the `parent_run_held` fact the handler derives from a
one-directional Operation -> Run read; these tests exercise it with
the flag directly.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _procedure(
    *,
    procedure_id: UUID | None = None,
    status: ProcedureStatus = ProcedureStatus.HELD,
) -> Procedure:
    return Procedure(
        id=procedure_id or uuid4(),
        name=ProcedureName("X"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=status,
        parent_run_id=None,
    )


@pytest.mark.unit
def test_decide_emits_procedure_resumed_when_held() -> None:
    proc = _procedure()
    events = resume_procedure.decide(
        state=proc,
        command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=3),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureResumed)
    assert events[0].procedure_id == proc.id
    assert events[0].re_establishment_boundary == 3
    assert events[0].occurred_at == _NOW
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id() -> None:
    proc = _procedure()
    decision_id = uuid4()
    events = resume_procedure.decide(
        state=proc,
        command=ResumeProcedure(
            procedure_id=proc.id,
            re_establishment_boundary=0,
            decided_by_decision_id=decision_id,
        ),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id


@pytest.mark.unit
def test_decide_rejects_when_parent_run_held() -> None:
    """Off-diagonal guard: a Held Procedure whose parent Run is Held cannot
    resume (it would walk real setpoints while the Run is paused)."""
    proc = _procedure()  # status Held
    with pytest.raises(ProcedureCannotResumeError) as exc:
        resume_procedure.decide(
            state=proc,
            command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=0),
            parent_run_held=True,
            now=_NOW,
        )
    assert exc.value.parent_run_held is True
    assert "parent Run is Held" in str(exc.value)


@pytest.mark.unit
def test_decide_allows_when_parent_run_not_held() -> None:
    """A Held Procedure whose parent Run is NOT Held resumes normally."""
    proc = _procedure()
    events = resume_procedure.decide(
        state=proc,
        command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=0),
        parent_run_held=False,
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureResumed)


@pytest.mark.unit
def test_decide_status_guard_precedes_parent_run_guard() -> None:
    """A non-Held Procedure raises the status-guard form even if the parent
    Run is also Held (status checked first; parent_run_held flag not set)."""
    proc = _procedure(status=ProcedureStatus.RUNNING)
    with pytest.raises(ProcedureCannotResumeError) as exc:
        resume_procedure.decide(
            state=proc,
            command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=0),
            parent_run_held=True,
            now=_NOW,
        )
    assert exc.value.parent_run_held is False
    assert exc.value.current_status is ProcedureStatus.RUNNING


@pytest.mark.unit
def test_decide_accepts_zero_boundary() -> None:
    """Boundary 0 = re-establish from the first step (valid)."""
    proc = _procedure()
    events = resume_procedure.decide(
        state=proc,
        command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=0),
        now=_NOW,
    )
    assert events[0].re_establishment_boundary == 0


@pytest.mark.unit
def test_decide_rejects_negative_boundary() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureReEstablishmentBoundaryError):
        resume_procedure.decide(
            state=proc,
            command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=-1),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        resume_procedure.decide(
            state=None,
            command=ResumeProcedure(procedure_id=pid, re_establishment_boundary=0),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ProcedureStatus.DEFINED,
        ProcedureStatus.RUNNING,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ],
)
def test_decide_rejects_non_held_status(status: ProcedureStatus) -> None:
    """Resuming a non-Held procedure raises (resuming a Running one too)."""
    proc = _procedure(status=status)
    with pytest.raises(ProcedureCannotResumeError) as exc:
        resume_procedure.decide(
            state=proc,
            command=ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=0),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = ResumeProcedure(procedure_id=proc.id, re_establishment_boundary=2)
    first = resume_procedure.decide(state=proc, command=cmd, now=_NOW)
    second = resume_procedure.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
