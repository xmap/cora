"""Unit tests for ShortfallSummaryProjection.

Pins the subscribed-event-types frozenset (projection-metadata
assertion) and the single INSERT-on-genesis apply path.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.data.aggregates.shortfall.state import ShortfallReason
from cora.data.projections import ShortfallSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_SHORTFALL_ID = uuid4()
_RUN_ID = uuid4()
_CAPTURE_PATH_ID = uuid4()
_RECORDED_BY = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_HOST = "tomdet"
_ROOT = "/local1/2BM"
_FILE_MODIFIED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_RUN_ENDED_AT = datetime(2026, 6, 10, 9, 5, 0, tzinfo=UTC)
_OCCURRED_AT = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Shortfall",
        stream_id=_SHORTFALL_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )


def _recorded_payload(
    *,
    commanded_projection_count: int | None = 1541,
    dropped_frame_count: int | None = 0,
) -> dict[str, Any]:
    return {
        "shortfall_id": str(_SHORTFALL_ID),
        "producing_run_id": str(_RUN_ID),
        "capture_path_id": str(_CAPTURE_PATH_ID),
        "host": _HOST,
        "root": _ROOT,
        "projection_count": 1,
        "commanded_projection_count": commanded_projection_count,
        "dropped_frame_count": dropped_frame_count,
        "reason": ShortfallReason.STRUCTURALLY_INCOMPLETE.value,
        "file_modified_at": _FILE_MODIFIED_AT.isoformat(),
        "run_ended_at": _RUN_ENDED_AT.isoformat(),
        "occurred_at": _OCCURRED_AT.isoformat(),
        "recorded_by": str(_RECORDED_BY),
    }


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = ShortfallSummaryProjection()
    assert proj.name == "proj_data_shortfall_summary"
    assert proj.subscribed_event_types == frozenset({"ShortfallRecorded"})


@pytest.mark.unit
async def test_shortfall_recorded_inserts_with_counts() -> None:
    proj = ShortfallSummaryProjection()
    conn = AsyncMock()
    event = _stored("ShortfallRecorded", _recorded_payload())
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_shortfall_summary" in sql
    assert "ON CONFLICT (shortfall_id) DO NOTHING" in sql
    assert "'Recorded'" in sql
    assert args.args[1] == _SHORTFALL_ID
    assert args.args[2] == _RUN_ID
    assert args.args[3] == _CAPTURE_PATH_ID
    assert args.args[4] == _HOST
    assert args.args[5] == _ROOT
    assert args.args[6] == 1
    assert args.args[7] == 1541
    assert args.args[8] == 0
    assert args.args[9] == ShortfallReason.STRUCTURALLY_INCOMPLETE.value
    assert args.args[10] == _FILE_MODIFIED_AT
    assert args.args[11] == _RUN_ENDED_AT
    assert args.args[12] == _OCCURRED_AT  # recorded_at <- occurred_at
    assert args.args[13] == _RECORDED_BY


@pytest.mark.unit
async def test_shortfall_recorded_inserts_with_null_counts() -> None:
    proj = ShortfallSummaryProjection()
    conn = AsyncMock()
    payload = _recorded_payload(commanded_projection_count=None, dropped_frame_count=None)
    await proj.apply(_stored("ShortfallRecorded", payload), conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] is None  # commanded_projection_count
    assert args.args[8] is None  # dropped_frame_count


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = ShortfallSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("UnrelatedEvent", {}), conn)
    conn.execute.assert_not_awaited()
