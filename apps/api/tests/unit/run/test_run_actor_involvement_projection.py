"""Unit tests for RunActorInvolvementProjection.

Pins per-event apply() dispatch: RunStarted INSERTs a starter row keyed by the
event's ENVELOPE principal_id + ENVELOPE occurred_at (not payload fields),
lifecycle events UPDATE status by run_id (RunResumed folds back to Running via
the same status map), and a RunStarted with no envelope principal is skipped.
The exact SQL constant per branch is asserted so a swap of INSERT/UPDATE would
fail. Postgres-side behavior (the actual rows + the in-flight filter) is in the
integration/lookup tests.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.projections import RunActorInvolvementProjection

_RUN_ID = uuid4()
_STARTER_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 7, 5, 14, 0, 0, tzinfo=UTC)
# Deliberately different from _NOW so a test can prove the INSERT uses the
# envelope occurred_at, never a payload["occurred_at"].
_PAYLOAD_TIME = datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, Any],
    *,
    principal_id: Any = _STARTER_ID,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Run",
        stream_id=_RUN_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=principal_id,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = RunActorInvolvementProjection()
    assert proj.name == "proj_run_actor_involvement"
    assert proj.subscribed_event_types == frozenset(
        {
            "RunStarted",
            "RunHeld",
            "RunResumed",
            "RunCompleted",
            "RunAborted",
            "RunStopped",
            "RunTruncated",
        }
    )


@pytest.mark.unit
async def test_run_started_inserts_starter_from_envelope_principal_and_time() -> None:
    conn = AsyncMock()
    proj = RunActorInvolvementProjection()
    await proj.apply(
        _stored(
            "RunStarted",
            {"run_id": str(_RUN_ID), "occurred_at": _PAYLOAD_TIME.isoformat()},
        ),
        conn,
    )
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    # The INSERT statement, then (principal_id, run_id, created_at). The starter
    # and the created_at both come from the ENVELOPE (event.principal_id +
    # event.occurred_at), never from payload: created_at is _NOW, not the
    # deliberately-stale payload occurred_at.
    assert "INSERT INTO proj_run_actor_involvement" in args[0]
    assert "ON CONFLICT (principal_id, run_id) DO NOTHING" in args[0]
    assert args[1] == _STARTER_ID
    assert args[2] == _RUN_ID
    assert args[3] == _NOW


@pytest.mark.unit
async def test_run_started_without_envelope_principal_is_skipped() -> None:
    conn = AsyncMock()
    proj = RunActorInvolvementProjection()
    await proj.apply(
        _stored(
            "RunStarted",
            {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
            principal_id=None,
        ),
        conn,
    )
    conn.execute.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [
        ("RunHeld", "Held"),
        ("RunResumed", "Running"),
        ("RunCompleted", "Completed"),
        ("RunAborted", "Aborted"),
        ("RunStopped", "Stopped"),
        ("RunTruncated", "Truncated"),
    ],
)
async def test_lifecycle_updates_status_by_run_id(event_type: str, expected_status: str) -> None:
    conn = AsyncMock()
    proj = RunActorInvolvementProjection()
    await proj.apply(_stored(event_type, {"run_id": str(_RUN_ID)}), conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    # The UPDATE statement (keyed by run_id), then (run_id, status). RunResumed
    # folds back to Running via the same status map, no separate SQL.
    assert "UPDATE proj_run_actor_involvement" in args[0]
    assert "WHERE run_id = $1" in args[0]
    assert args[1] == _RUN_ID
    assert args[2] == expected_status


@pytest.mark.unit
async def test_unsubscribed_event_is_a_noop() -> None:
    conn = AsyncMock()
    proj = RunActorInvolvementProjection()
    await proj.apply(_stored("RunAdjusted", {"run_id": str(_RUN_ID)}), conn)
    conn.execute.assert_not_awaited()
