"""Unit tests for RatificationCoverageProjection (consequence gate coverage).

Pins per-event apply() dispatch against a mocked connection: RatificationRequested
INSERTs a Requested row carrying target_action_id + command_name from the genesis
payload; Granted/Denied UPDATE status by ratification_id; an unsubscribed event is
a no-op. The Postgres-side behavior (the actual rows + the Granted filter) is in
the integration/lookup test.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.trust.projections import RatificationCoverageProjection

_RATIFICATION_ID = uuid4()
_RUN_ID = uuid4()
_NOW = datetime(2026, 7, 6, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Ratification",
        stream_id=_RATIFICATION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = RatificationCoverageProjection()
    assert proj.name == "proj_trust_ratification_coverage"
    assert proj.subscribed_event_types == frozenset(
        {"RatificationRequested", "RatificationGranted", "RatificationDenied"}
    )


@pytest.mark.unit
async def test_requested_inserts_scope_from_genesis_payload() -> None:
    conn = AsyncMock()
    proj = RatificationCoverageProjection()
    await proj.apply(
        _stored(
            "RatificationRequested",
            {
                "ratification_id": str(_RATIFICATION_ID),
                "target_action_id": str(_RUN_ID),
                "command_name": "StopRun",
                "consequence_class": "irreversible",
                "requested_by": str(uuid4()),
                "occurred_at": _NOW.isoformat(),
            },
        ),
        conn,
    )
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert "INSERT INTO proj_trust_ratification_coverage" in args[0]
    assert args[1] == _RATIFICATION_ID
    assert args[2] == _RUN_ID
    assert args[3] == "StopRun"
    # created_at is the envelope occurred_at.
    assert args[4] == _NOW


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event_type", "expected_status"),
    [("RatificationGranted", "Granted"), ("RatificationDenied", "Denied")],
)
async def test_transition_updates_status_by_ratification_id(
    event_type: str, expected_status: str
) -> None:
    conn = AsyncMock()
    proj = RatificationCoverageProjection()
    payload = {"ratification_id": str(_RATIFICATION_ID), "occurred_at": _NOW.isoformat()}
    await proj.apply(_stored(event_type, payload), conn)
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert "UPDATE proj_trust_ratification_coverage" in args[0]
    assert args[1] == _RATIFICATION_ID
    assert args[2] == expected_status


@pytest.mark.unit
async def test_unsubscribed_event_is_a_noop() -> None:
    conn = AsyncMock()
    proj = RatificationCoverageProjection()
    await proj.apply(_stored("PolicyDefined", {"ratification_id": str(_RATIFICATION_ID)}), conn)
    conn.execute.assert_not_awaited()
