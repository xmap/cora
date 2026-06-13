"""ProcedureName VO + ProcedureStatus enum + Operation BC error class tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.operation.aggregates.procedure import (
    LOGBOOK_KIND_ACTIVITY,
    PROCEDURE_NAME_MAX_LENGTH,
    STEP_KIND_VALUES,
    STEPS_LOGBOOK_SCHEMA,
    InvalidProcedureAbortReasonError,
    InvalidProcedureInterruptedAtError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    InvalidProcedureTruncateReasonError,
    InvalidStepKindError,
    ProcedureAbortReason,
    ProcedureAlreadyExistsError,
    ProcedureCannotAbortError,
    ProcedureCannotCompleteError,
    ProcedureCannotStartError,
    ProcedureCannotTruncateError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureStatus,
    ProcedureStepsLogbookClosedError,
    ProcedureTruncateReason,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH

# ---------- ProcedureName VO ----------


@pytest.mark.unit
def test_procedure_name_trims_whitespace() -> None:
    assert ProcedureName("  Vessel-A bakeout  ").value == "Vessel-A bakeout"


@pytest.mark.unit
def test_procedure_name_rejects_empty() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("")


@pytest.mark.unit
def test_procedure_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("   ")


@pytest.mark.unit
def test_procedure_name_accepts_max_length() -> None:
    name = "x" * PROCEDURE_NAME_MAX_LENGTH
    assert ProcedureName(name).value == name


@pytest.mark.unit
def test_procedure_name_rejects_over_max_length() -> None:
    with pytest.raises(InvalidProcedureNameError):
        ProcedureName("x" * (PROCEDURE_NAME_MAX_LENGTH + 1))


# ---------- ProcedureStatus enum ----------


@pytest.mark.unit
def test_procedure_status_values_locked() -> None:
    """Pin the 5-state FSM values; future additions must be a deliberate test edit.
    The FSM was REVISED from BC map's `Idle/Starting/Running/Verifying/Complete/Aborted`
    per standards-corpus research at [[project_operation_design]]: Verifying is NOT
    standards-blessed at FSM level; transient states deferred per Run BC precedent."""
    assert ProcedureStatus.DEFINED.value == "Defined"
    assert ProcedureStatus.RUNNING.value == "Running"
    assert ProcedureStatus.COMPLETED.value == "Completed"
    assert ProcedureStatus.ABORTED.value == "Aborted"
    assert ProcedureStatus.TRUNCATED.value == "Truncated"
    assert {s.value for s in ProcedureStatus} == {
        "Defined",
        "Running",
        "Completed",
        "Aborted",
        "Truncated",
    }


# ---------- Error class shapes ----------


@pytest.mark.unit
def test_invalid_procedure_name_error_carries_value() -> None:
    err = InvalidProcedureNameError("")
    assert err.value == ""
    assert "1-200" in str(err)


@pytest.mark.unit
def test_invalid_procedure_kind_error_carries_value() -> None:
    err = InvalidProcedureKindError("x" * 51)
    assert err.value == "x" * 51
    assert "1-50" in str(err)


@pytest.mark.unit
def test_procedure_already_exists_error_carries_id() -> None:
    procedure_id = uuid4()
    err = ProcedureAlreadyExistsError(procedure_id)
    assert err.procedure_id == procedure_id
    assert str(procedure_id) in str(err)


@pytest.mark.unit
def test_procedure_not_found_error_carries_id() -> None:
    procedure_id = uuid4()
    err = ProcedureNotFoundError(procedure_id)
    assert err.procedure_id == procedure_id
    assert str(procedure_id) in str(err)


# ---------- 10c-b: ProcedureAbortReason VO ----------


@pytest.mark.unit
def test_procedure_abort_reason_trims_whitespace() -> None:
    assert ProcedureAbortReason("  vacuum loss  ").value == "vacuum loss"


@pytest.mark.unit
def test_procedure_abort_reason_rejects_empty() -> None:
    with pytest.raises(InvalidProcedureAbortReasonError):
        ProcedureAbortReason("")


@pytest.mark.unit
def test_procedure_abort_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidProcedureAbortReasonError):
        ProcedureAbortReason("   ")


@pytest.mark.unit
def test_procedure_abort_reason_accepts_max_length() -> None:
    reason = "x" * REASON_MAX_LENGTH
    assert ProcedureAbortReason(reason).value == reason


@pytest.mark.unit
def test_procedure_abort_reason_rejects_over_max_length() -> None:
    with pytest.raises(InvalidProcedureAbortReasonError):
        ProcedureAbortReason("x" * (REASON_MAX_LENGTH + 1))


@pytest.mark.unit
def test_invalid_procedure_abort_reason_error_carries_value() -> None:
    err = InvalidProcedureAbortReasonError("")
    assert err.value == ""
    assert "1-500" in str(err)


# ---------- 10c-b: transition-guard error classes ----------


@pytest.mark.unit
def test_procedure_cannot_start_error_carries_id_and_status() -> None:
    procedure_id = uuid4()
    err = ProcedureCannotStartError(procedure_id, current_status=ProcedureStatus.RUNNING)
    assert err.procedure_id == procedure_id
    assert err.current_status is ProcedureStatus.RUNNING
    assert str(procedure_id) in str(err)
    assert "Running" in str(err)
    assert "Defined" in str(err)


@pytest.mark.unit
def test_procedure_cannot_complete_error_carries_id_and_status() -> None:
    procedure_id = uuid4()
    err = ProcedureCannotCompleteError(procedure_id, current_status=ProcedureStatus.DEFINED)
    assert err.procedure_id == procedure_id
    assert err.current_status is ProcedureStatus.DEFINED
    assert "Defined" in str(err)
    assert "Running" in str(err)


@pytest.mark.unit
def test_procedure_cannot_abort_error_carries_id_and_status() -> None:
    procedure_id = uuid4()
    err = ProcedureCannotAbortError(procedure_id, current_status=ProcedureStatus.COMPLETED)
    assert err.procedure_id == procedure_id
    assert err.current_status is ProcedureStatus.COMPLETED
    assert "Completed" in str(err)
    assert "Running" in str(err)


@pytest.mark.unit
def test_procedure_asset_decommissioned_error_carries_ids() -> None:
    a, b = uuid4(), uuid4()
    err = ProcedurePlanAssetDecommissionedError([a, b])
    assert err.asset_ids == [a, b]
    assert str(a) in str(err)
    assert str(b) in str(err)


# ---------- step logbook constants + errors ----------


@pytest.mark.unit
def test_step_kind_values_locked() -> None:
    """Pin the 3 step kinds; future additions must be a deliberate test edit.
    Reflects CORA's rename of ISA-106's Command/Perform/Verify triplet."""
    assert frozenset({"setpoint", "action", "check"}) == STEP_KIND_VALUES


@pytest.mark.unit
def test_logbook_kind_activity_constant() -> None:
    assert LOGBOOK_KIND_ACTIVITY == "activity"


@pytest.mark.unit
def test_steps_logbook_schema_declares_step_kind_and_timestamps() -> None:
    """Schema declares the wrapper columns; per-kind body lives at the API layer."""
    field_names = set(STEPS_LOGBOOK_SCHEMA.fields)
    # Wrapper columns:
    assert "step_kind" in field_names
    assert "sampled_at" in field_names
    assert "occurred_at" in field_names
    assert "recorded_at" in field_names
    # Polymorphic JSON body NOT declared in schema (LogbookFieldType is
    # closed over primitives); per-kind shape lives in code.
    assert "payload" not in field_names


@pytest.mark.unit
def test_invalid_step_kind_error_carries_value_and_allowed() -> None:
    err = InvalidStepKindError("bogus", STEP_KIND_VALUES)
    assert err.value == "bogus"
    assert err.allowed == STEP_KIND_VALUES
    assert "bogus" in str(err)
    assert "setpoint" in str(err)


@pytest.mark.unit
def test_procedure_steps_logbook_closed_error_carries_id_and_status() -> None:
    procedure_id = uuid4()
    err = ProcedureStepsLogbookClosedError(procedure_id, current_status=ProcedureStatus.COMPLETED)
    assert err.procedure_id == procedure_id
    assert err.current_status is ProcedureStatus.COMPLETED
    assert "Completed" in str(err)
    assert "Running" in str(err)


# ---------- ProcedureTruncateReason VO + truncate-related errors ----------


_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_procedure_truncate_reason_trims_whitespace() -> None:
    assert ProcedureTruncateReason("  weekend power loss  ").value == "weekend power loss"


@pytest.mark.unit
def test_procedure_truncate_reason_rejects_empty() -> None:
    with pytest.raises(InvalidProcedureTruncateReasonError):
        ProcedureTruncateReason("")


@pytest.mark.unit
def test_procedure_truncate_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidProcedureTruncateReasonError):
        ProcedureTruncateReason("   ")


@pytest.mark.unit
def test_procedure_truncate_reason_accepts_max_length() -> None:
    reason = "x" * REASON_MAX_LENGTH
    assert ProcedureTruncateReason(reason).value == reason


@pytest.mark.unit
def test_procedure_truncate_reason_rejects_over_max_length() -> None:
    with pytest.raises(InvalidProcedureTruncateReasonError):
        ProcedureTruncateReason("x" * (REASON_MAX_LENGTH + 1))


@pytest.mark.unit
def test_invalid_procedure_truncate_reason_error_carries_value() -> None:
    err = InvalidProcedureTruncateReasonError("")
    assert err.value == ""
    assert "1-500" in str(err)


@pytest.mark.unit
def test_procedure_cannot_truncate_error_carries_id_and_status() -> None:
    procedure_id = uuid4()
    err = ProcedureCannotTruncateError(procedure_id, current_status=ProcedureStatus.COMPLETED)
    assert err.procedure_id == procedure_id
    assert err.current_status is ProcedureStatus.COMPLETED
    assert "Completed" in str(err)
    assert "Running" in str(err)


@pytest.mark.unit
def test_invalid_procedure_interrupted_at_error_carries_timestamps() -> None:
    future = _NOW + timedelta(hours=1)
    err = InvalidProcedureInterruptedAtError(future, _NOW)
    assert err.interrupted_at == future
    assert err.now == _NOW
    assert future.isoformat() in str(err)
    assert "future" in str(err).lower()
