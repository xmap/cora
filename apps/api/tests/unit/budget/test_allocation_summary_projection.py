"""Unit tests for AllocationSummaryProjection.

Pins per-event-type apply() dispatch for the 5 subscribed Allocation
lifecycle events. Postgres-side behavior is in the integration suite
(test_allocation_lookup_postgres.py exercises the read path). Mirrors
test_language_model_summary_projection.py.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.budget.projections import AllocationSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ALLOCATION_ID = uuid4()
_CAMPAIGN_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 7, 13, 9, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Allocation",
        stream_id=_ALLOCATION_ID,
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
    proj = AllocationSummaryProjection()
    assert proj.name == "proj_budget_allocation_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "AllocationGranted",
            "AllocationActivated",
            "AllocationCeilingUpdated",
            "AllocationSealed",
            "AllocationVoided",
        }
    )


@pytest.mark.unit
async def test_allocation_granted_inserts_with_granted_status() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationGranted",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "ceiling_usd": 25000.0,
            "campaign_id": str(_CAMPAIGN_ID),
            "note": "FY26 imaging award",
            "granted_by": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_budget_allocation_summary" in sql
    assert "ON CONFLICT (allocation_id) DO NOTHING" in sql
    assert "'Granted'" in sql
    assert args.args[1] == _ALLOCATION_ID
    assert args.args[2] == 25000.0
    assert args.args[3] == _CAMPAIGN_ID
    assert args.args[4] == "FY26 imaging award"
    assert args.args[5] == _NOW


@pytest.mark.unit
async def test_allocation_granted_without_campaign_inserts_null_binding() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationGranted",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "ceiling_usd": 100.0,
            "campaign_id": None,
            "note": "unbound envelope",
            "granted_by": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[3] is None


@pytest.mark.unit
async def test_allocation_activated_updates_status_and_activated_at() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationActivated",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "activated_by": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_budget_allocation_summary" in sql
    assert "SET status = 'Active'" in sql
    assert "activated_at = $2" in sql
    assert args.args[1] == _ALLOCATION_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_ceiling_updated_overwrites_ceiling_without_status_change() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationCeilingUpdated",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "ceiling_usd": 12000.0,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_budget_allocation_summary" in sql
    assert "SET ceiling_usd = $2" in sql
    assert "status" not in sql
    assert args.args[1] == _ALLOCATION_ID
    assert args.args[2] == 12000.0


@pytest.mark.unit
async def test_allocation_sealed_updates_status_timestamp_and_snapshot() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationSealed",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "spent_usd": 431.25,
            "reason": "Campaign closed",
            "sealed_by": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_budget_allocation_summary" in sql
    assert "SET status = 'Sealed'" in sql
    assert "sealed_at = $2" in sql
    assert "spent_usd_at_seal = $3" in sql
    assert args.args[1] == _ALLOCATION_ID
    assert args.args[2] == _NOW
    assert args.args[3] == 431.25


@pytest.mark.unit
async def test_allocation_voided_updates_status_only() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AllocationVoided",
        {
            "allocation_id": str(_ALLOCATION_ID),
            "reason": "granted by mistake",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_budget_allocation_summary" in sql
    assert "SET status = 'Voided'" in sql
    assert args.args[1] == _ALLOCATION_ID


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = AllocationSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
