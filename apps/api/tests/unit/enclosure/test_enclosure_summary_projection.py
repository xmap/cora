"""Unit tests for EnclosureSummaryProjection.

Pins per-event-type apply() dispatch + idempotency for the 3
subscribed Enclosure events. Postgres-side behavior (real UNIQUE
constraint, real bookmark advance) is in the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure.projections.enclosure import EnclosureSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId, MonitorSourceId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))
_TEST_MONITOR_SOURCE_ID = MonitorSourceId(UUID("00000000-0000-0000-0000-000000000002"))

_ENCLOSURE_ID = uuid4()
_FACILITY_CODE = "aps"
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _conn_with_savepoint() -> AsyncMock:
    """AsyncMock conn whose `transaction()` returns an async context manager.

    The projection's `EnclosureRegistered` arm wraps its INSERT in
    `async with conn.transaction(): ...` so the
    `(facility_code, name) WHERE lifecycle='Active'` partial
    UNIQUE constraint on `proj_enclosure_summary` rolls back only the
    inner SAVEPOINT (not the worker's outer batch txn). The unit test
    mock needs to satisfy that protocol shape.
    """
    conn = AsyncMock()
    transaction_cm = AsyncMock()
    transaction_cm.__aenter__.return_value = None
    transaction_cm.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=transaction_cm)
    return conn


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Enclosure",
        stream_id=_ENCLOSURE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=_TEST_ACTOR_ID,
    )


@pytest.mark.unit
def test_projection_metadata() -> None:
    """Per feedback_projection_metadata_test: static frozenset assertion
    guards against silent subscription drift across CI parallelization.
    Extending this assertion is mandatory whenever a new event
    subscription is added."""
    proj = EnclosureSummaryProjection()
    assert proj.name == "proj_enclosure_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "EnclosureRegistered",
            "EnclosurePermitObserved",
            "EnclosureDecommissioned",
        }
    )


@pytest.mark.unit
def test_projection_does_not_subscribe_to_unrelated_events() -> None:
    """Asset / Facility / Supply events belong to other projections."""
    proj = EnclosureSummaryProjection()
    for foreign in (
        "AssetRegistered",
        "FacilityRegistered",
        "SupplyRegistered",
        "RunStarted",
    ):
        assert foreign not in proj.subscribed_event_types


# ---------- EnclosureRegistered apply ----------


@pytest.mark.unit
async def test_enclosure_registered_inserts_with_unknown_permit_and_active_lifecycle() -> None:
    proj = EnclosureSummaryProjection()
    conn = _conn_with_savepoint()
    event = _stored(
        "EnclosureRegistered",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "name": "2-BM Hutch A",
            "facility_code": _FACILITY_CODE,
            "registered_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    conn.transaction.assert_called_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_enclosure_summary" in sql
    assert "ON CONFLICT (enclosure_id) DO NOTHING" in sql
    assert "'Unknown'" in sql
    assert "'Active'" in sql
    assert args.args[1] == _ENCLOSURE_ID
    assert args.args[2] == "2-BM Hutch A"
    assert args.args[3] == _FACILITY_CODE
    assert args.args[4] == _NOW
    assert args.args[5] == _TEST_ACTOR_ID


@pytest.mark.unit
async def test_enclosure_registered_swallows_unique_violation_and_logs_warn() -> None:
    """Cross-stream duplicate on (facility_code, name) raises
    UniqueViolation inside the SAVEPOINT; the projection catches it,
    logs, and returns cleanly so the worker's outer batch txn can keep
    advancing."""
    proj = EnclosureSummaryProjection()
    conn = _conn_with_savepoint()
    conn.execute.side_effect = asyncpg.UniqueViolationError("duplicate (facility_code, name)")
    event = _stored(
        "EnclosureRegistered",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "name": "2-BM Hutch A",
            "facility_code": _FACILITY_CODE,
            "registered_by": str(_TEST_ACTOR_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.transaction.assert_called_once()
    conn.execute.assert_awaited_once()


# ---------- EnclosurePermitObserved apply ----------


@pytest.mark.unit
async def test_enclosure_permit_observed_updates_status_and_observation_envelope() -> None:
    """Splits `monitor_ref` 'kind:id' substream attribution into
    `last_source_kind` and `last_source_id` columns so consumers can
    query `WHERE last_source_kind = 'EpicsPv'` without LIKE-substring
    fragility (per L-proj-2)."""
    proj = EnclosureSummaryProjection()
    conn = AsyncMock()
    observed_at = datetime(2026, 6, 9, 14, 30, 0, tzinfo=UTC)
    event = _stored(
        "EnclosurePermitObserved",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "from_status": "Unknown",
            "to_status": "Permitted",
            "reason": "PSS interlock chain healthy",
            "trigger": "Monitor",
            "triggered_by": str(_TEST_MONITOR_SOURCE_ID),
            "occurred_at": observed_at.isoformat(),
            "monitor_ref": "EpicsPv:2bma:PSS:permit",
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_enclosure_summary" in sql
    assert args.args[1] == _ENCLOSURE_ID
    assert args.args[2] == "Permitted"
    assert args.args[3] == observed_at
    assert args.args[4] == "PSS interlock chain healthy"
    assert args.args[5] == "Monitor"
    assert args.args[6] == "EpicsPv"
    assert args.args[7] == "2bma:PSS:permit"


@pytest.mark.unit
async def test_enclosure_permit_observed_handles_absent_monitor_ref_as_null_source() -> None:
    """`monitor_ref` is omit-when-None on the wire per the convention
    shared with Supply transition events; the projection writes
    `last_source_kind` and `last_source_id` as NULL when absent."""
    proj = EnclosureSummaryProjection()
    conn = AsyncMock()
    observed_at = datetime(2026, 6, 9, 14, 30, 0, tzinfo=UTC)
    event = _stored(
        "EnclosurePermitObserved",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "from_status": "Permitted",
            "to_status": "NotPermitted",
            "reason": "EPS shutter closed pending survey",
            "trigger": "Monitor",
            "triggered_by": str(_TEST_MONITOR_SOURCE_ID),
            "occurred_at": observed_at.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[2] == "NotPermitted"
    assert args.args[6] is None
    assert args.args[7] is None


@pytest.mark.unit
async def test_permit_observed_monitor_ref_without_separator_routes_to_kind_only() -> None:
    """`monitor_ref` without a ':' separator routes the full string to
    `last_source_kind` and leaves `last_source_id` NULL. Defensive
    branch in `_split_monitor_ref` for adapters that emit a single-
    token reference (no source-instance disambiguator)."""
    proj = EnclosureSummaryProjection()
    conn = AsyncMock()
    observed_at = datetime(2026, 6, 9, 14, 30, 0, tzinfo=UTC)
    event = _stored(
        "EnclosurePermitObserved",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "from_status": "Unknown",
            "to_status": "Permitted",
            "reason": "operator-attested grant",
            "trigger": "Monitor",
            "triggered_by": str(_TEST_MONITOR_SOURCE_ID),
            "occurred_at": observed_at.isoformat(),
            "monitor_ref": "Operator",
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[6] == "Operator"
    assert args.args[7] is None


# ---------- EnclosureDecommissioned apply ----------


@pytest.mark.unit
async def test_enclosure_decommissioned_updates_lifecycle_and_terminal_audit() -> None:
    """Lifecycle flips to Decommissioned and the terminal attribution
    pair (`decommissioned_at`, `decommissioned_by`) lands; permit_status
    is preserved untouched per the orthogonality lock."""
    proj = EnclosureSummaryProjection()
    conn = AsyncMock()
    decommissioned_at = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
    event = _stored(
        "EnclosureDecommissioned",
        {
            "enclosure_id": str(_ENCLOSURE_ID),
            "reason": "enclosure consolidated into adjacent hutch",
            "triggered_by": str(_TEST_ACTOR_ID),
            "occurred_at": decommissioned_at.isoformat(),
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_enclosure_summary" in sql
    assert "'Decommissioned'" in sql
    # D6.L2 orthogonality guard: terminal transition MUST NOT touch
    # permit_status. Locks the audit-preservation invariant before the
    # observe slice can violate it.
    assert "permit_status" not in sql
    assert args.args[1] == _ENCLOSURE_ID
    assert args.args[2] == decommissioned_at
    assert args.args[3] == _TEST_ACTOR_ID


# ---------- Foreign event guard ----------


@pytest.mark.unit
async def test_projection_ignores_unsubscribed_event_type() -> None:
    """Foreign event types passed to apply() are no-ops (the worker
    should never deliver them, but defensive guard ensures we don't
    crash on contamination)."""
    proj = EnclosureSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("ImaginaryEvent", {}), conn)
    conn.execute.assert_not_awaited()
