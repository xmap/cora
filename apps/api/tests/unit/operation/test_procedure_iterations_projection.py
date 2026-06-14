"""Unit tests for ProcedureIterationsProjection.

Pins per-event-type apply() dispatch + SQL arg ordering for the two
subscribed iteration boundary events. Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.projections import ProcedureIterationsProjection

_PROCEDURE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Procedure",
        stream_id=_PROCEDURE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = ProcedureIterationsProjection()
    assert proj.name == "proj_operation_procedure_iterations"
    assert proj.subscribed_event_types == frozenset(
        {"ProcedureIterationStarted", "ProcedureIterationEnded"}
    )


@pytest.mark.unit
async def test_iteration_started_inserts_row() -> None:
    proj = ProcedureIterationsProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureIterationStarted",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "iteration_index": 2,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "INSERT INTO proj_operation_procedure_iterations" in sql
    assert "ON CONFLICT (procedure_id, iteration_index) DO NOTHING" in sql
    assert conn.execute.call_args.args[1] == _PROCEDURE_ID
    assert conn.execute.call_args.args[2] == 2
    assert conn.execute.call_args.args[3] == _NOW


@pytest.mark.unit
async def test_iteration_ended_updates_verdict_and_timing() -> None:
    proj = ProcedureIterationsProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureIterationEnded",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "iteration_index": 2,
            "converged": True,
            "reason": "within tolerance",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "UPDATE proj_operation_procedure_iterations" in sql
    assert "WHERE procedure_id = $1 AND iteration_index = $2" in sql
    args = conn.execute.call_args.args
    assert args[1] == _PROCEDURE_ID
    assert args[2] == 2
    assert args[3] == _NOW
    assert args[4] is True
    assert args[5] == "within tolerance"


@pytest.mark.unit
async def test_iteration_ended_passes_null_verdict_and_reason() -> None:
    proj = ProcedureIterationsProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureIterationEnded",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "iteration_index": 1,
            "converged": None,
            "reason": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.call_args.args
    assert args[4] is None
    assert args[5] is None


@pytest.mark.unit
async def test_unsubscribed_event_type_is_no_op() -> None:
    proj = ProcedureIterationsProjection()
    conn = AsyncMock()
    await proj.apply(_stored("ProcedureRegistered", {"procedure_id": str(_PROCEDURE_ID)}), conn)
    conn.execute.assert_not_awaited()
