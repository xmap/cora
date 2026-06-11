"""Unit tests for AssetSummaryProjection's commissioned_at /
decommissioned_at column writes (slice E.1).

Postgres round-trip behavior lives in the integration suite; this
file pins the SQL shape and bind-arg semantics via an AsyncMock
connection (mirrors `test_asset_summary_projection.py` precedent).
Per section 10 of project_asset_persistent_id_design.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.equipment.projections.asset import AssetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000001"))

_ASSET_ID = uuid4()
_PARENT_ID = uuid4()
_NOW = datetime(2026, 6, 4, 14, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 4, 18, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Asset",
        stream_id=_ASSET_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_projection_writes_commissioned_at_on_register() -> None:
    """AssetRegistered carries occurred_at; the projection writes it
    into the commissioned_at column (and also into created_at)."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "X",
            "tier": "Unit",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "commissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "commissioned_at" in sql
    assert args.args[11] == _NOW


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_projection_writes_decommissioned_at_on_decommission() -> None:
    """AssetDecommissioned writes both lifecycle='Decommissioned' and
    decommissioned_at=occurred_at via a dedicated SQL statement."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetDecommissioned",
        {
            "asset_id": str(_ASSET_ID),
            "occurred_at": _LATER.isoformat(),
            "decommissioned_by": str(_TEST_ACTOR_ID),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "decommissioned_at" in sql
    assert "lifecycle = 'Decommissioned'" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == _LATER


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_projection_subscribes_to_lifecycle_timestamp_events() -> None:
    """AssetRegistered and AssetDecommissioned remain in the projection's
    subscribed event types (slice E.1 does not narrow the subscription
    list)."""
    proj = AssetSummaryProjection()
    assert "AssetRegistered" in proj.subscribed_event_types
    assert "AssetDecommissioned" in proj.subscribed_event_types


@pytest.mark.unit
@pytest.mark.timeout(60, method="thread")
async def test_projection_does_not_write_decommissioned_at_on_activate() -> None:
    """Non-decommission lifecycle transitions must NOT touch the
    decommissioned_at column: the dedicated SQL statement fires only
    on AssetDecommissioned."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetActivated",
        {"asset_id": str(_ASSET_ID), "occurred_at": _LATER.isoformat()},
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "decommissioned_at" not in sql
