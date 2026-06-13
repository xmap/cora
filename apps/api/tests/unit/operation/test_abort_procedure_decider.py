"""Pure-decider tests for `abort_procedure` slice.

Single-source emergency-exit terminal: `Running -> Aborted`. Reason
field validated via `ProcedureAbortReason` VO (1-500 chars after
trim).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InvalidProcedureAbortReasonError,
    Procedure,
    ProcedureAborted,
    ProcedureCannotAbortError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
)
from cora.operation.features import abort_procedure
from cora.operation.features.abort_procedure import AbortProcedure
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
def test_decide_emits_procedure_aborted_when_running() -> None:
    proc = _procedure()
    events = abort_procedure.decide(
        state=proc,
        command=AbortProcedure(procedure_id=proc.id, reason="vacuum loss"),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureAborted)
    assert events[0].procedure_id == proc.id
    assert events[0].reason == "vacuum loss"
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_reason_via_vo() -> None:
    proc = _procedure()
    events = abort_procedure.decide(
        state=proc,
        command=AbortProcedure(procedure_id=proc.id, reason="  hardware fault  "),
        now=_NOW,
    )
    assert events[0].reason == "hardware fault"


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        abort_procedure.decide(
            state=None,
            command=AbortProcedure(procedure_id=pid, reason="x"),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    """Validation order: VO check happens before status check, surfaces 400 not 409
    even when transitioning from a wrong-status state."""
    proc = _procedure()
    with pytest.raises(InvalidProcedureAbortReasonError):
        abort_procedure.decide(
            state=proc,
            command=AbortProcedure(procedure_id=proc.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureAbortReasonError):
        abort_procedure.decide(
            state=proc,
            command=AbortProcedure(procedure_id=proc.id, reason="x" * (REASON_MAX_LENGTH + 1)),
            now=_NOW,
        )


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
    with pytest.raises(ProcedureCannotAbortError) as exc:
        abort_procedure.decide(
            state=proc,
            command=AbortProcedure(procedure_id=proc.id, reason="x"),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = AbortProcedure(procedure_id=proc.id, reason="quench")
    first = abort_procedure.decide(state=proc, command=cmd, now=_NOW)
    second = abort_procedure.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
