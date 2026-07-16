"""Unit tests for LanguageModelSummaryProjection.

Pins per-event-type apply() dispatch for the 5 subscribed
LanguageModel lifecycle events. Postgres-side behavior is in the
integration suite. Mirrors test_agent_summary_projection.py.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.agent.projections import LanguageModelSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_LANGUAGE_MODEL_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 7, 12, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="LanguageModel",
        stream_id=_LANGUAGE_MODEL_ID,
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
    proj = LanguageModelSummaryProjection()
    assert proj.name == "proj_agent_language_model_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "LanguageModelDefined",
            "LanguageModelApproved",
            "LanguageModelRetirementAnnounced",
            "LanguageModelRetired",
            "LanguageModelDeprecated",
        }
    )


@pytest.mark.unit
async def test_language_model_defined_inserts_with_defined_status() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "LanguageModelDefined",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "name": "Claude Sonnet 4.6",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
            "served_via": "Direct",
            "endpoint_note": None,
            "cost_basis": {"kind": "GpuHourPricing", "usd_per_gpu_hour": 2.5},
            "data_tier": "Internal",
            "archivability": "Alias",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_agent_language_model_summary" in sql
    assert "ON CONFLICT (language_model_id) DO NOTHING" in sql
    assert "'Defined'" in sql
    assert args.args[1] == _LANGUAGE_MODEL_ID
    assert args.args[2] == "Claude Sonnet 4.6"
    assert args.args[3] == "anthropic"
    assert args.args[4] == "claude-sonnet-4-6"
    assert args.args[5] is None
    assert args.args[6] == "Direct"
    assert args.args[7] == "Internal"
    assert args.args[8] == "Alias"
    assert args.args[9] == _NOW


@pytest.mark.unit
async def test_language_model_approved_updates_status_and_approved_at() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "LanguageModelApproved",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_language_model_summary" in sql
    assert "SET status = 'Approved'" in sql
    assert "approved_at = $2" in sql
    assert args.args[1] == _LANGUAGE_MODEL_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_retirement_announced_updates_status_and_both_retirement_timestamps() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    effective = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)
    event = _stored(
        "LanguageModelRetirementAnnounced",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "reason": "Provider EOL notice",
            "effective_at": effective.isoformat(),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_language_model_summary" in sql
    assert "SET status = 'RetirementAnnounced'" in sql
    assert "retirement_announced_at = $2" in sql
    assert "retirement_effective_at = $3" in sql
    assert args.args[1] == _LANGUAGE_MODEL_ID
    assert args.args[2] == _NOW
    assert args.args[3] == effective


@pytest.mark.unit
async def test_retirement_announced_without_date_writes_null_effective_at() -> None:
    """The vendor gave a warning but no cutoff date: the announcement
    timestamp lands, the effective column stays NULL."""
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "LanguageModelRetirementAnnounced",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "reason": "Provider EOL notice, no date yet",
            "effective_at": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == _NOW
    assert args.args[3] is None


@pytest.mark.unit
async def test_language_model_retired_updates_status_and_retired_at() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "LanguageModelRetired",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "reason": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_language_model_summary" in sql
    assert "SET status = 'Retired'" in sql
    assert "retired_at = $2" in sql
    assert args.args[1] == _LANGUAGE_MODEL_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_language_model_deprecated_updates_status_and_deprecated_at() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "LanguageModelDeprecated",
        {
            "language_model_id": str(_LANGUAGE_MODEL_ID),
            "reason": "Facility withdrew approval",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_agent_language_model_summary" in sql
    assert "SET status = 'Deprecated'" in sql
    assert "deprecated_at = $2" in sql
    assert args.args[1] == _LANGUAGE_MODEL_ID
    assert args.args[2] == _NOW


@pytest.mark.unit
async def test_unknown_event_type_falls_through_match() -> None:
    proj = LanguageModelSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
