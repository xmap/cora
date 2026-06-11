"""Unit tests for AcquisitionSummaryProjection.

Pins the subscribed-event-types frozenset (projection-metadata
assertion) and the single INSERT-on-genesis apply path.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.data.projections import AcquisitionSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_ACQUISITION_ID = uuid4()
_DATASET_ID = uuid4()
_ASSET_ID = uuid4()
_RUN_ID = uuid4()
_RECORDED_BY = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_OCCURRED_AT = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Acquisition",
        stream_id=_ACQUISITION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_OCCURRED_AT,
        recorded_at=_OCCURRED_AT,
    )


def _recorded_payload(*, producing_run_id: str | None = None) -> dict[str, Any]:
    return {
        "acquisition_id": str(_ACQUISITION_ID),
        "dataset_id": str(_DATASET_ID),
        "producing_asset_id": str(_ASSET_ID),
        "producing_run_id": producing_run_id,
        "captured_at": _CAPTURED_AT.isoformat(),
        "settings": {"exposure_ms": 200},
        "evidence": {"frames": 1801},
        "occurred_at": _OCCURRED_AT.isoformat(),
        "recorded_by": str(_RECORDED_BY),
    }


@pytest.mark.unit
def test_projection_metadata() -> None:
    proj = AcquisitionSummaryProjection()
    assert proj.name == "proj_data_acquisition_summary"
    assert proj.subscribed_event_types == frozenset({"AcquisitionRecorded"})


@pytest.mark.unit
async def test_acquisition_recorded_inserts_with_run() -> None:
    proj = AcquisitionSummaryProjection()
    conn = AsyncMock()
    event = _stored("AcquisitionRecorded", _recorded_payload(producing_run_id=str(_RUN_ID)))
    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_acquisition_summary" in sql
    assert "ON CONFLICT (acquisition_id) DO NOTHING" in sql
    assert "'Recorded'" in sql
    assert args.args[1] == _ACQUISITION_ID
    assert args.args[2] == _DATASET_ID
    assert args.args[3] == _ASSET_ID
    assert args.args[4] == _RUN_ID
    assert args.args[5] == _CAPTURED_AT
    assert args.args[8] == _OCCURRED_AT  # recorded_at <- occurred_at
    assert args.args[9] == _RECORDED_BY


@pytest.mark.unit
async def test_acquisition_recorded_inserts_with_null_run() -> None:
    proj = AcquisitionSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("AcquisitionRecorded", _recorded_payload(producing_run_id=None)), conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # producing_run_id


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = AcquisitionSummaryProjection()
    conn = AsyncMock()
    await proj.apply(_stored("UnrelatedEvent", {}), conn)
    conn.execute.assert_not_awaited()
