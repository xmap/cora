"""Pure-decider tests for `hold_procedure` slice.

Single-source pause transition: `Running -> Held`. Reason field
validated via `ProcedureHoldReason` VO (1-500 chars after trim).
Mirrors `hold_run`; the state name is `Held` (Procedure is an
execution-FSM sibling of Run), with a REQUIRED reason (unlike
slim `RunHeld`).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InvalidProcedureHoldReasonError,
    Procedure,
    ProcedureCannotHoldError,
    ProcedureHeld,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import hold_procedure
from cora.operation.features.hold_procedure import HoldProcedure
from cora.shared.text_bounds import REASON_MAX_LENGTH

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
def test_decide_emits_procedure_held_when_running() -> None:
    proc = _procedure()
    events = hold_procedure.decide(
        state=proc,
        command=HoldProcedure(procedure_id=proc.id, reason="beam dropped"),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureHeld)
    assert events[0].procedure_id == proc.id
    assert events[0].reason == "beam dropped"
    assert events[0].occurred_at == _NOW
    assert events[0].decided_by_decision_id is None


@pytest.mark.unit
def test_decide_threads_decided_by_decision_id() -> None:
    proc = _procedure()
    decision_id = uuid4()
    events = hold_procedure.decide(
        state=proc,
        command=HoldProcedure(
            procedure_id=proc.id, reason="autonomous hold", decided_by_decision_id=decision_id
        ),
        now=_NOW,
    )
    assert events[0].decided_by_decision_id == decision_id


@pytest.mark.unit
def test_decide_trims_reason_via_vo() -> None:
    proc = _procedure()
    events = hold_procedure.decide(
        state=proc,
        command=HoldProcedure(procedure_id=proc.id, reason="  investigating fault  "),
        now=_NOW,
    )
    assert events[0].reason == "investigating fault"


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        hold_procedure.decide(
            state=None,
            command=HoldProcedure(procedure_id=pid, reason="x"),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureHoldReasonError):
        hold_procedure.decide(
            state=proc,
            command=HoldProcedure(procedure_id=proc.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureHoldReasonError):
        hold_procedure.decide(
            state=proc,
            command=HoldProcedure(procedure_id=proc.id, reason="x" * (REASON_MAX_LENGTH + 1)),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ProcedureStatus.DEFINED,
        ProcedureStatus.HELD,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ],
)
def test_decide_rejects_non_running_status(status: ProcedureStatus) -> None:
    """Holding a non-Running procedure raises (re-holding a Held one too)."""
    proc = _procedure(status=status)
    with pytest.raises(ProcedureCannotHoldError) as exc:
        hold_procedure.decide(
            state=proc,
            command=HoldProcedure(procedure_id=proc.id, reason="x"),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = HoldProcedure(procedure_id=proc.id, reason="break")
    first = hold_procedure.decide(state=proc, command=cmd, now=_NOW)
    second = hold_procedure.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
