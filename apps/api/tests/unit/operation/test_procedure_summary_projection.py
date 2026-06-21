"""Unit tests for ProcedureSummaryProjection.

Pins per-event-type apply() dispatch + SQL arg ordering for the 6
subscribed Procedure events. Postgres-side behavior (jsonb roundtrip
+ UUID[] GIN-index queries) is in the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.projections import ProcedureSummaryProjection

_PROCEDURE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


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
    proj = ProcedureSummaryProjection()
    assert proj.name == "proj_operation_procedure_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "ProcedureRegistered",
            "ProcedureStarted",
            "ProcedureCompleted",
            "ProcedureAborted",
            "ProcedureTruncated",
            "ProcedureHeld",
            "ProcedureResumed",
            "ProcedureActivitiesLogbookOpened",
            "ProcedureIterationStarted",
        }
    )


@pytest.mark.unit
def test_projection_does_not_subscribe_to_unrelated_events() -> None:
    proj = ProcedureSummaryProjection()
    for foreign in ("AssetRegistered", "RunStarted", "SubjectMounted", "SupplyRegistered"):
        assert foreign not in proj.subscribed_event_types


@pytest.mark.unit
def test_projection_does_not_subscribe_to_iteration_ended() -> None:
    # iteration_count tracks iterations begun; the convergence-verdict
    # projection from ProcedureIterationEnded is a deferred watch item.
    proj = ProcedureSummaryProjection()
    assert "ProcedureIterationEnded" not in proj.subscribed_event_types


@pytest.mark.unit
def test_projection_subscribes_to_hold_resume() -> None:
    """Resumable conduct now surfaces Held in the read model: migration
    20260621060000 widened the `status` CHECK to admit 'Held', so the
    projection folds ProcedureHeld -> status='Held' and ProcedureResumed ->
    status='Running'. See [[project_resumable_conduct_design]]."""
    proj = ProcedureSummaryProjection()
    assert "ProcedureHeld" in proj.subscribed_event_types
    assert "ProcedureResumed" in proj.subscribed_event_types


@pytest.mark.unit
async def test_procedure_registered_inserts_with_defined_status_and_null_audit() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    asset_a, asset_b = uuid4(), uuid4()
    parent_run = uuid4()
    event = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "name": "Vessel-A bakeout",
            "kind": "bakeout",
            "target_asset_ids": [str(asset_a), str(asset_b)],
            "parent_run_id": str(parent_run),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.call_args.args
    # Pin the idempotency marker at the unit tier (mirrors the supply
    # projection's ON CONFLICT assertion).
    assert "ON CONFLICT (procedure_id) DO NOTHING" in args[0]
    assert args[1] == _PROCEDURE_ID
    assert args[2] == "Vessel-A bakeout"
    assert args[3] == "bakeout"
    assert args[4] == [asset_a, asset_b]
    assert args[5] == parent_run
    assert args[6] == _NOW


@pytest.mark.unit
async def test_procedure_registered_handles_null_parent_run() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "name": "X",
            "kind": "bakeout",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.call_args.args
    assert args[4] == []
    assert args[5] is None


# NOTE: the 6 status-change UPDATE arms (Started/Completed/Aborted/Truncated/
# Held/Resumed) use literal status strings in SQL via per-event SQL constants.
# The old "hoist to a parameterized `_UPDATE_STATUS_SQL` at the 5th arm" plan
# was re-evaluated when Held/Resumed landed and dropped: the arms are NOT
# uniform (Truncated also sets interrupted_at, Resumed CLEARS the reason), so a
# single parameterized SQL reads worse. These substring assertions stay.


@pytest.mark.unit
async def test_procedure_started_updates_status_to_running() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureStarted",
        {"procedure_id": str(_PROCEDURE_ID), "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Running'" in sql
    assert conn.execute.call_args.args[1] == _PROCEDURE_ID
    assert conn.execute.call_args.args[2] == _NOW


@pytest.mark.unit
async def test_procedure_completed_updates_status_to_completed() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureCompleted",
        {"procedure_id": str(_PROCEDURE_ID), "occurred_at": _NOW.isoformat()},
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Completed'" in sql


@pytest.mark.unit
async def test_procedure_aborted_updates_status_and_reason() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureAborted",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "reason": "vacuum loss",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Aborted'" in sql
    assert conn.execute.call_args.args[3] == "vacuum loss"


@pytest.mark.unit
async def test_procedure_truncated_updates_status_reason_and_interrupted_at() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    interrupted_at = datetime(2026, 5, 14, 8, 0, 0, tzinfo=UTC)
    event = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "reason": "weekend power loss",
            "interrupted_at": interrupted_at.isoformat(),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Truncated'" in sql
    assert conn.execute.call_args.args[3] == "weekend power loss"
    assert conn.execute.call_args.args[4] == interrupted_at


@pytest.mark.unit
async def test_procedure_truncated_handles_null_interrupted_at() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureTruncated",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "reason": "unknown",
            "interrupted_at": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    assert conn.execute.call_args.args[4] is None


@pytest.mark.unit
async def test_procedure_held_updates_status_and_reason() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureHeld",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "reason": "beam dropped",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Held'" in sql
    assert conn.execute.call_args.args[1] == _PROCEDURE_ID
    assert conn.execute.call_args.args[2] == _NOW
    assert conn.execute.call_args.args[3] == "beam dropped"


@pytest.mark.unit
async def test_procedure_resumed_updates_status_to_running_and_clears_reason() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureResumed",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "re_establishment_boundary": 0,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET status = 'Running'" in sql
    assert "last_status_reason = NULL" in sql
    assert conn.execute.call_args.args[1] == _PROCEDURE_ID
    assert conn.execute.call_args.args[2] == _NOW


@pytest.mark.unit
async def test_procedure_steps_logbook_opened_updates_logbook_id() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    logbook_id = uuid4()
    event = _stored(
        "ProcedureActivitiesLogbookOpened",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "logbook_id": str(logbook_id),
            "kind": "activity",
            "schema": {"fields": {}, "description": ""},
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "activity_logbook_id = $2" in sql
    assert conn.execute.call_args.args[2] == logbook_id


@pytest.mark.unit
async def test_unsubscribed_event_type_is_no_op() -> None:
    """Defensive guard: foreign event types in the dispatch are silently skipped."""
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored("BogusEvent", {"procedure_id": str(_PROCEDURE_ID)})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_procedure_registered_seeds_iteration_count_to_zero() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureRegistered",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "name": "X",
            "kind": "center_alignment",
            "target_asset_ids": [],
            "parent_run_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "iteration_count" in sql
    # iteration_count is seeded with the literal 0 (no positional arg).
    assert ", 0)" in sql.replace("\n", " ").replace("  ", " ")


@pytest.mark.unit
async def test_iteration_started_sets_iteration_count_to_index() -> None:
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureIterationStarted",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "iteration_index": 3,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    sql = conn.execute.call_args.args[0]
    assert "SET iteration_count = $2" in sql
    assert conn.execute.call_args.args[1] == _PROCEDURE_ID
    assert conn.execute.call_args.args[2] == 3


@pytest.mark.unit
async def test_iteration_ended_is_no_op_for_projection() -> None:
    # Not subscribed: the worker would not deliver it, and the defensive
    # dispatch skips it without a write.
    proj = ProcedureSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "ProcedureIterationEnded",
        {
            "procedure_id": str(_PROCEDURE_ID),
            "iteration_index": 1,
            "converged": True,
            "reason": None,
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
