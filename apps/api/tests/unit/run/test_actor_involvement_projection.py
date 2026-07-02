"""Unit tests for RunActorInvolvementProjection.

Pins per-event-type apply() dispatch for the cross-stream projection:
the starter row comes from the RunStarted envelope principal_id; the
supervisor row comes from a RunSupervision DecisionRegistered payload;
lifecycle events drive status for all rows of a run. Postgres-side
behavior (real CHECK, partial index, lookup) is in the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.projections import RunActorInvolvementProjection

_RUN_ID = uuid4()
_STARTER_ID = uuid4()
_SUPERVISOR_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 7, 2, 14, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, Any],
    *,
    stream_type: str = "Run",
    principal_id: UUID | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type=stream_type,
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
            "DecisionRegistered",
        }
    )


@pytest.mark.unit
async def test_run_started_inserts_starter_from_envelope_principal() -> None:
    """The starter row keys on the RunStarted envelope principal_id, not a
    payload field (RunStarted carries no actor in its payload)."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
        principal_id=_STARTER_ID,
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql, actor_id, run_id, _created = args.args
    assert "INSERT INTO proj_run_actor_involvement" in sql
    assert "'starter'" in sql
    assert "ON CONFLICT" in sql
    assert actor_id == _STARTER_ID
    assert run_id == _RUN_ID


@pytest.mark.unit
async def test_run_started_without_principal_is_skipped() -> None:
    """No envelope principal -> no actor to be behind the run -> no write."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(
        "RunStarted",
        {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()},
        principal_id=None,
    )

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_run_supervision_decision_inserts_supervisor_row() -> None:
    """A RunSupervision DecisionRegistered inserts a supervisor row keyed on
    decided_by, for the run_id in the decision inputs."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decided_by": str(_SUPERVISOR_ID),
            "context": "RunSupervision",
            "inputs": {"run_id": str(_RUN_ID)},
            "occurred_at": _NOW.isoformat(),
        },
        stream_type="Decision",
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql, actor_id, run_id, _created = args.args
    assert "INSERT INTO proj_run_actor_involvement" in sql
    assert "'supervisor'" in sql
    # The supervisor row copies status from the existing starter row and is
    # guarded on the starter row existing (no phantom supervisor row for a
    # run with no starter). This SELECT-from-starter shape is the intricate
    # part; pin it here since it is otherwise only exercised in integration.
    assert "involvement_kind = 'starter'" in sql
    assert "starter.status" in sql
    assert actor_id == _SUPERVISOR_ID
    assert run_id == _RUN_ID


@pytest.mark.unit
@pytest.mark.parametrize("other_context", ["EnergyChange", "OperatorAbort", "DebriefConflicted"])
async def test_non_supervision_decision_is_ignored(other_context: str) -> None:
    """Only RunSupervision-context Decisions map to a supervisor row; every
    other Decision context is skipped (this is the cross-stream guard)."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decided_by": str(_SUPERVISOR_ID),
            "context": other_context,
            "inputs": {"run_id": str(_RUN_ID)},
            "occurred_at": _NOW.isoformat(),
        },
        stream_type="Decision",
    )

    await proj.apply(event, conn)

    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_supervision_decision_without_run_id_is_skipped() -> None:
    """A RunSupervision Decision missing inputs.run_id cannot be attributed
    to a run, so it is skipped rather than crashing the projection."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(
        "DecisionRegistered",
        {
            "decided_by": str(_SUPERVISOR_ID),
            "context": "RunSupervision",
            "inputs": {},
            "occurred_at": _NOW.isoformat(),
        },
        stream_type="Decision",
    )

    await proj.apply(event, conn)

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
async def test_lifecycle_event_updates_status_for_all_rows(
    event_type: str, expected_status: str
) -> None:
    """A lifecycle transition updates status for every row of the run_id
    (starter + any supervisors), not a single actor row."""
    proj = RunActorInvolvementProjection()
    conn = AsyncMock()
    event = _stored(event_type, {"run_id": str(_RUN_ID), "occurred_at": _NOW.isoformat()})

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql, run_id, status = args.args
    assert "UPDATE proj_run_actor_involvement" in sql
    assert "WHERE run_id = $1" in sql
    assert run_id == _RUN_ID
    assert status == expected_status
