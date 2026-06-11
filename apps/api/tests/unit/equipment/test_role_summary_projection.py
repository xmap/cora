"""Unit tests for RoleSummaryProjection.

Pins the per-event-type apply() dispatch for the single subscribed
Role event at 3A (RoleDefined). Postgres-side behavior is in the
integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections import RoleSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ROLE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 10, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Role",
        stream_id=_ROLE_ID,
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
    proj = RoleSummaryProjection()
    assert proj.name == "proj_equipment_role_summary"
    assert proj.subscribed_event_types == frozenset({"RoleDefined"})


@pytest.mark.unit
async def test_projection_does_not_subscribe_to_family_events() -> None:
    """Family events belong in FamilySummaryProjection."""
    proj = RoleSummaryProjection()
    assert "FamilyDefined" not in proj.subscribed_event_types


@pytest.mark.unit
async def test_role_defined_inserts_with_full_contract_payload() -> None:
    proj = RoleSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RoleDefined",
        {
            "role_id": str(_ROLE_ID),
            "name": "Imager",
            "docstring": "Acquires 2D image frames on exposure or trigger.",
            "occurred_at": _NOW.isoformat(),
            "required_affordances": ["Imageable"],
            "optional_affordances": ["Binnable"],
            "produces": ["Image"],
            "consumes": ["TriggerIn"],
        },
    )

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_equipment_role_summary" in sql
    assert "ON CONFLICT (role_id) DO NOTHING" in sql
    assert args.args[1] == _ROLE_ID
    assert args.args[2] == "Imager"
    assert args.args[3] == "Acquires 2D image frames on exposure or trigger."
    assert args.args[4] == ["Imageable"]
    assert args.args[5] == ["Binnable"]
    assert args.args[6] == ["Image"]
    assert args.args[7] == ["TriggerIn"]
    assert args.args[8] == _NOW


@pytest.mark.unit
async def test_role_defined_tolerates_sparse_collection_fields() -> None:
    """Additive-state pattern: payload predating an additive field
    defaults to an empty list (mirrors RoleDefined.from_stored
    posture). The projection passes through whatever is in the
    payload + defaults missing keys to []."""
    proj = RoleSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "RoleDefined",
        {
            "role_id": str(_ROLE_ID),
            "name": "Bare",
            "docstring": "x",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] == []
    assert args.args[5] == []
    assert args.args[6] == []
    assert args.args[7] == []


@pytest.mark.unit
async def test_apply_ignores_unknown_event_types() -> None:
    proj = RoleSummaryProjection()
    conn = AsyncMock()
    event = _stored("SomethingElse", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_called()
