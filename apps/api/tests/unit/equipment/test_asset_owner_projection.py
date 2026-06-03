"""Unit tests for the AssetSummaryProjection owners SQL paths.

Postgres round-trip behaviour lives in
`tests/integration/equipment/test_asset_owner_projection_pg.py`; this
suite pins the SQL shape and bind-arg semantics via an AsyncMock
connection (mirrors `test_asset_summary_projection.py` precedent).
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections.asset import AssetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ASSET_ID = uuid4()
_PARENT_ID = uuid4()
_NOW = datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC)


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
async def test_projection_writes_owners_on_register() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "X",
            "level": "Unit",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "owners": [
                {
                    "name": "HZB",
                    "contact": "ops@hzb.de",
                    "identifier": None,
                    "identifier_type": None,
                }
            ],
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_asset_summary" in sql
    # arg index 10 is the owners list (alternate_identifiers is 9).
    assert args.args[10] == [
        {
            "name": "HZB",
            "contact": "ops@hzb.de",
            "identifier": None,
            "identifier_type": None,
        }
    ]


@pytest.mark.unit
async def test_projection_omits_owners_defaults_to_empty_list_on_register() -> None:
    """Legacy AssetRegistered events omit the `owners` key; the
    projection writes the canonical empty list."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "X",
            "level": "Unit",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[10] == []


@pytest.mark.unit
async def test_projection_sorts_owners_by_name_ascending_on_register() -> None:
    """The canonical helper sorts by `name` so the persisted bytes
    match the deterministic order regardless of payload ordering."""
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetRegistered",
        {
            "asset_id": str(_ASSET_ID),
            "name": "X",
            "level": "Unit",
            "parent_id": str(_PARENT_ID),
            "occurred_at": _NOW.isoformat(),
            "owners": [
                {"name": "HZB", "contact": None, "identifier": None, "identifier_type": None},
                {"name": "APS", "contact": None, "identifier": None, "identifier_type": None},
                {"name": "ESRF", "contact": None, "identifier": None, "identifier_type": None},
            ],
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    names = [entry["name"] for entry in args.args[10]]
    assert names == ["APS", "ESRF", "HZB"]


@pytest.mark.unit
async def test_projection_appends_owner_on_added_event() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetOwnerAdded",
        {
            "asset_id": str(_ASSET_ID),
            "owner": {
                "name": "HZB",
                "contact": None,
                "identifier": None,
                "identifier_type": None,
            },
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "owners" in sql
    assert "ORDER BY elem->>'name'" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2]["name"] == "HZB"


@pytest.mark.unit
async def test_projection_removes_owner_by_name_on_removed_event() -> None:
    proj = AssetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AssetOwnerRemoved",
        {
            "asset_id": str(_ASSET_ID),
            "owner_name": "HZB",
            "occurred_at": _NOW.isoformat(),
        },
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_asset_summary" in sql
    assert "owners" in sql
    assert "elem->>'name'" in sql
    assert args.args[1] == _ASSET_ID
    assert args.args[2] == "HZB"


@pytest.mark.unit
async def test_projection_subscribes_to_owner_events() -> None:
    proj = AssetSummaryProjection()
    assert "AssetOwnerAdded" in proj.subscribed_event_types
    assert "AssetOwnerRemoved" in proj.subscribed_event_types
