"""Pure-decider tests for `truncate_procedure` slice.

Single-source partial-data terminal: `Running -> Truncated`. Reason
field validated via `ProcedureTruncateReason` VO (1-500 chars after
trim). `interrupted_at` optional but must not be in the future.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    InvalidProcedureInterruptedAtError,
    InvalidProcedureTruncateReasonError,
    Procedure,
    ProcedureCannotTruncateError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureTruncated,
)
from cora.operation.features import truncate_procedure
from cora.operation.features.truncate_procedure import TruncateProcedure
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
def test_decide_emits_procedure_truncated_when_running() -> None:
    proc = _procedure()
    interrupted_at = _NOW - timedelta(hours=2)
    events = truncate_procedure.decide(
        state=proc,
        command=TruncateProcedure(
            procedure_id=proc.id,
            reason="weekend power loss",
            interrupted_at=interrupted_at,
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureTruncated)
    assert events[0].procedure_id == proc.id
    assert events[0].reason == "weekend power loss"
    assert events[0].interrupted_at == interrupted_at
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_emits_procedure_truncated_when_held() -> None:
    """Resumable conduct: a paused (Held) Procedure that became de-facto
    dead can be truncated retroactively."""
    proc = _procedure(status=ProcedureStatus.HELD)
    events = truncate_procedure.decide(
        state=proc,
        command=TruncateProcedure(
            procedure_id=proc.id,
            reason="paused over the weekend, hardware died",
            interrupted_at=None,
        ),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureTruncated)
    assert events[0].procedure_id == proc.id


@pytest.mark.unit
def test_decide_accepts_none_interrupted_at() -> None:
    """interrupted_at is optional; None is valid (operator doesn't know when)."""
    proc = _procedure()
    events = truncate_procedure.decide(
        state=proc,
        command=TruncateProcedure(procedure_id=proc.id, reason="unknown when crashed"),
        now=_NOW,
    )
    assert events[0].interrupted_at is None


@pytest.mark.unit
def test_decide_trims_reason_via_vo() -> None:
    proc = _procedure()
    events = truncate_procedure.decide(
        state=proc,
        command=TruncateProcedure(procedure_id=proc.id, reason="  vacuum loss  "),
        now=_NOW,
    )
    assert events[0].reason == "vacuum loss"


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        truncate_procedure.decide(
            state=None,
            command=TruncateProcedure(procedure_id=pid, reason="x"),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
def test_decide_rejects_whitespace_only_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureTruncateReasonError):
        truncate_procedure.decide(
            state=proc,
            command=TruncateProcedure(procedure_id=proc.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_too_long_reason() -> None:
    proc = _procedure()
    with pytest.raises(InvalidProcedureTruncateReasonError):
        truncate_procedure.decide(
            state=proc,
            command=TruncateProcedure(
                procedure_id=proc.id,
                reason="x" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_future_interrupted_at() -> None:
    proc = _procedure()
    future = _NOW + timedelta(hours=1)
    with pytest.raises(InvalidProcedureInterruptedAtError) as exc:
        truncate_procedure.decide(
            state=proc,
            command=TruncateProcedure(procedure_id=proc.id, reason="x", interrupted_at=future),
            now=_NOW,
        )
    assert exc.value.interrupted_at == future
    assert exc.value.now == _NOW


@pytest.mark.unit
def test_decide_accepts_interrupted_at_equal_to_now() -> None:
    """Boundary: interrupted_at == now is NOT in the future; allowed."""
    proc = _procedure()
    events = truncate_procedure.decide(
        state=proc,
        command=TruncateProcedure(procedure_id=proc.id, reason="r", interrupted_at=_NOW),
        now=_NOW,
    )
    assert events[0].interrupted_at == _NOW


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
    with pytest.raises(ProcedureCannotTruncateError) as exc:
        truncate_procedure.decide(
            state=proc,
            command=TruncateProcedure(procedure_id=proc.id, reason="x"),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_is_pure_same_input_same_output() -> None:
    proc = _procedure()
    cmd = TruncateProcedure(procedure_id=proc.id, reason="weekend crash")
    first = truncate_procedure.decide(state=proc, command=cmd, now=_NOW)
    second = truncate_procedure.decide(state=proc, command=cmd, now=_NOW)
    assert first == second
