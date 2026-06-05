"""Unit tests for FixtureSummaryProjection's FixturePersistentIdAssigned handling.

Pins the JSONB-shape contract for the persistent_id column written by
the projection when a FixturePersistentIdAssigned event lands. The
neighbor `test_fixture_summary_projection.py` covers the projector's
genesis arm; this file isolates the Phase-2 PIDINST arm so a regression
in the JSONB-build SQL or the (scheme, value) carry surfaces as a
focused failure. Integration-tier real-PG behavior (replay, codecs)
lives in `tests/integration/`.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.equipment.projections.fixture_summary import FixtureSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

pytestmark = [pytest.mark.unit, pytest.mark.timeout(60, method="thread")]

_FIXTURE_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Fixture",
        stream_id=_FIXTURE_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _persistent_id_assigned(
    *, scheme: str = "DOI", value: str = "10.5281/zenodo.7654321"
) -> StoredEvent:
    return _stored(
        "FixturePersistentIdAssigned",
        {
            "fixture_id": str(_FIXTURE_ID),
            "persistent_id_scheme": scheme,
            "persistent_id_value": value,
            "occurred_at": _NOW.isoformat(),
        },
    )


async def test_apply_assigned_writes_persistent_id_jsonb() -> None:
    proj = FixtureSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="DOI", value="10.5281/zenodo.7654321")

    await proj.apply(event, conn)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_equipment_fixture_summary" in sql
    assert "SET persistent_id" in sql
    assert "jsonb_build_object" in sql
    assert "WHERE fixture_id = $1" in sql
    assert args.args[1] == _FIXTURE_ID
    assert args.args[2] == "DOI"
    assert args.args[3] == "10.5281/zenodo.7654321"


async def test_jsonb_shape_is_scheme_value_object() -> None:
    proj = FixtureSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="Handle", value="20.500.12613/67890")

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "'scheme'" in sql
    assert "'value'" in sql
    assert "$2::text" in sql
    assert "$3::text" in sql
    assert args.args[2] == "Handle"
    assert args.args[3] == "20.500.12613/67890"


async def test_apply_twice_with_same_event_is_idempotent_at_jsonb_column_level() -> None:
    proj = FixtureSummaryProjection()
    conn = AsyncMock()
    event = _persistent_id_assigned(scheme="DOI", value="10.5281/zenodo.7654321")

    await proj.apply(event, conn)
    await proj.apply(event, conn)

    assert conn.execute.await_count == 2
    first, second = conn.execute.await_args_list
    assert first.args == second.args
    sql = first.args[0]
    assert "UPDATE proj_equipment_fixture_summary" in sql
    assert "SET persistent_id" in sql
    assert first.args[1] == _FIXTURE_ID
    assert first.args[2] == "DOI"
    assert first.args[3] == "10.5281/zenodo.7654321"
