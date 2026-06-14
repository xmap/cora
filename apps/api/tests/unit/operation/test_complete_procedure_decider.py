"""Pure-decider tests for `complete_procedure` slice.

Single-source happy-path terminal: `Running -> Completed`. Mirrors
`complete_run`. Re-completing or completing from any non-Running
state raises.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _procedure(
    *,
    procedure_id: UUID | None = None,
    status: ProcedureStatus = ProcedureStatus.RUNNING,
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
def test_decide_emits_procedure_completed_when_running() -> None:
    proc = _procedure()
    events = complete_procedure.decide(
        state=proc,
        command=CompleteProcedure(procedure_id=proc.id),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureCompleted)
    assert events[0].procedure_id == proc.id
    assert events[0].occurred_at == _NOW
    # No actuation kind supplied -> the terminal event carries None.
    assert events[0].actuation_kind is None


@pytest.mark.unit
@pytest.mark.parametrize("kind", ["Physical", "Simulated", "Hybrid"])
def test_decide_snapshots_actuation_kind_onto_completed_event(kind: str) -> None:
    """The Conductor supplies the observed actuation kind on the command; the
    decider snapshots it verbatim onto ProcedureCompleted (the gate carrier)."""
    proc = _procedure()
    events = complete_procedure.decide(
        state=proc,
        command=CompleteProcedure(procedure_id=proc.id, actuation_kind=kind),
        now=_NOW,
    )
    assert events[0].actuation_kind == kind


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        complete_procedure.decide(
            state=None,
            command=CompleteProcedure(procedure_id=pid),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ProcedureStatus.DEFINED,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ],
)
def test_decide_rejects_non_running_status(status: ProcedureStatus) -> None:
    proc = _procedure(status=status)
    with pytest.raises(ProcedureCannotCompleteError) as exc:
        complete_procedure.decide(
            state=proc,
            command=CompleteProcedure(procedure_id=proc.id),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = CompleteProcedure(procedure_id=proc.id)
    first = complete_procedure.decide(state=proc, command=cmd, now=_NOW)
    second = complete_procedure.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
