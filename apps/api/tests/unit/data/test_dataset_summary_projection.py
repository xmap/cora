"""Unit tests for DatasetSummaryProjection."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from cora.data.projections import DatasetSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_DATASET_ID = uuid4()
_RUN_ID = uuid4()
_SUBJECT_ID = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 5, 13, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Dataset",
        stream_id=_DATASET_ID,
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
    proj = DatasetSummaryProjection()
    assert proj.name == "proj_data_dataset_summary"
    assert proj.subscribed_event_types == frozenset({"DatasetRegistered", "DatasetDiscarded"})


@pytest.mark.unit
async def test_dataset_registered_inserts_with_genesis_refs() -> None:
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DatasetRegistered",
        {
            "dataset_id": str(_DATASET_ID),
            "name": "tomo-001.h5",
            "uri": "s3://bucket/tomo-001.h5",
            "checksum": {"algorithm": "sha256", "value": "deadbeef"},
            "byte_size": 1024,
            "media_type": "application/x-hdf5",
            "conforms_to": [],
            "producing_run_id": str(_RUN_ID),
            "subject_id": str(_SUBJECT_ID),
            "derived_from": [],
            "occurred_at": _NOW.isoformat(),
            # compat exercised by
            # test_dataset_registered_without_used_calibration_ids_key_falls_back_to_empty_list.
            "used_calibration_ids": [],
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_dataset_summary" in sql
    assert "ON CONFLICT (dataset_id) DO NOTHING" in sql
    assert "'Registered'" in sql
    assert args.args[1] == _DATASET_ID
    assert args.args[2] == "tomo-001.h5"
    assert args.args[3] == "s3://bucket/tomo-001.h5"
    assert args.args[4] == _RUN_ID
    assert args.args[5] == _SUBJECT_ID
    assert args.args[6] == _NOW

    # not pinned. P0 gate-review fix: pin args[7] so a regression that
    # drops or misorders the projection's UUID[] parameter fails loud
    # at the unit tier instead of slipping through to integration.
    assert args.args[7] == []


@pytest.mark.unit
async def test_dataset_registered_with_null_run_and_subject() -> None:
    """Datasets without a producing Run or measured Subject."""
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DatasetRegistered",
        {
            "dataset_id": str(_DATASET_ID),
            "name": "imported.h5",
            "uri": "s3://bucket/imported.h5",
            "checksum": {"algorithm": "sha256", "value": "cafe" * 16},
            "producing_run_id": None,
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[4] is None  # producing_run_id
    assert args.args[5] is None  # subject_id


@pytest.mark.unit
async def test_dataset_registered_without_used_calibration_ids_key_falls_back_to_empty_list() -> (
    None
):
    """Legacy DatasetRegistered events lack the `used_calibration_ids`
    key in the payload entirely. The projection's `payload.get(
    "used_calibration_ids", [])` fallback MUST land an empty UUID list
    on the column so legacy rows backfill cleanly (matches the
    in-memory frozenset default + the from_stored forward-compat
    fold)."""
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DatasetRegistered",
        {
            "dataset_id": str(_DATASET_ID),
            "name": "legacy.h5",
            "uri": "s3://bucket/legacy.h5",
            "checksum": {"algorithm": "sha256", "value": "cafe" * 16},
            "producing_run_id": None,
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # NOTE: used_calibration_ids deliberately ABSENT
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert args.args[7] == []


@pytest.mark.unit
async def test_dataset_registered_with_citations_inserts_uuid_array() -> None:
    """When the payload carries `used_calibration_ids`, the
    projection parses each entry into a UUID and passes the list as
    the 7th arg. The decider sorts before emit, so the on-the-wire
    order is deterministic; the projection passes through verbatim."""
    cal_a = uuid4()
    cal_b = uuid4()
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DatasetRegistered",
        {
            "dataset_id": str(_DATASET_ID),
            "name": "cited-recon.h5",
            "uri": "s3://bucket/cited-recon.h5",
            "checksum": {"algorithm": "sha256", "value": "cafe" * 16},
            "producing_run_id": None,
            "subject_id": None,
            "occurred_at": _NOW.isoformat(),
            # Sorted (decider's responsibility); projection trusts.
            "used_calibration_ids": sorted([str(cal_a), str(cal_b)]),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    # Each entry parsed back into UUID and passed to the SQL execute.
    cited: list[Any] = args.args[7]
    assert isinstance(cited, list)
    assert set(cited) == {cal_a, cal_b}


@pytest.mark.unit
async def test_dataset_discarded_updates_status_only() -> None:
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "DatasetDiscarded",
        {
            "dataset_id": str(_DATASET_ID),
            "reason": "GDPR right-to-be-forgotten request",
            "occurred_at": _NOW.isoformat(),
        },
    )

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_data_dataset_summary" in sql
    assert "SET status = 'Discarded'" in sql
    assert "producing_run_id" not in sql
    assert "subject_id" not in sql
    assert args.args[1] == _DATASET_ID


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = DatasetSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()
