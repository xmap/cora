"""Unit tests for DistributionSummaryProjection."""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from asyncpg.exceptions import UniqueViolationError

from cora.data.projections import DistributionSummaryProjection
from cora.infrastructure.ports.event_store import StoredEvent

_DISTRIBUTION_ID = uuid4()
_DATASET_ID = uuid4()
_SUPPLY_ID = uuid4()
_REGISTERED_BY = uuid4()
_EVENT_ID = uuid4()
_CORRELATION_ID = uuid4()
_NOW = datetime(2026, 6, 9, 14, 0, 0, tzinfo=UTC)


def _stored(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Distribution",
        stream_id=_DISTRIBUTION_ID,
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _registered_payload() -> dict[str, Any]:
    return {
        "distribution_id": str(_DISTRIBUTION_ID),
        "dataset_id": str(_DATASET_ID),
        "supply_id": str(_SUPPLY_ID),
        "uri": "s3://bucket/key.h5",
        "checksum": {"algorithm": "sha256", "value": "deadbeef" * 8},
        "byte_size": 1024,
        "encoding": {
            "media_type": "application/x-hdf5",
            "conforms_to": ["https://manual.nexusformat.org/"],
        },
        "access_protocol": "S3",
        "occurred_at": _NOW.isoformat(),
        "registered_by": str(_REGISTERED_BY),
    }


@pytest.mark.unit
def test_projection_metadata() -> None:
    """Subscribed to three event types: DistributionRegistered for the
    genesis INSERT, AttestationRecorded for the projection-side
    Verified/Stale status flip (per project-data-attestation-design
    Slice C), and DistributionDiscarded for the terminal Discard flip
    (the discard_distribution slice's guarded primitive)."""
    proj = DistributionSummaryProjection()
    assert proj.name == "proj_data_distribution_summary"
    assert proj.subscribed_event_types == frozenset(
        {"DistributionRegistered", "AttestationRecorded", "DistributionDiscarded"}
    )


@pytest.mark.unit
async def test_distribution_registered_inserts_all_fields() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("DistributionRegistered", _registered_payload())

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "INSERT INTO proj_data_distribution_summary" in sql
    assert "ON CONFLICT (distribution_id) DO NOTHING" in sql
    assert "'Registered'" in sql

    assert args.args[1] == _DISTRIBUTION_ID
    assert args.args[2] == _DATASET_ID
    assert args.args[3] == _SUPPLY_ID
    assert args.args[4] == "s3://bucket/key.h5"
    # checksum + encoding are JSONB; the writer pre-serializes dicts to
    # strings for asyncpg's $N::jsonb cast.
    assert json.loads(args.args[5]) == {"algorithm": "sha256", "value": "deadbeef" * 8}
    assert args.args[6] == 1024
    assert json.loads(args.args[7]) == {
        "media_type": "application/x-hdf5",
        "conforms_to": ["https://manual.nexusformat.org/"],
    }
    assert args.args[8] == "S3"
    assert args.args[9] == _NOW
    assert args.args[10] == _REGISTERED_BY


@pytest.mark.unit
async def test_distribution_registered_swallows_unique_violation() -> None:
    """Per L31 / Supply projection-writer precedent: the partial UNIQUE
    INDEX collision on (dataset_id, supply_id, uri) is caught, logged
    WARN, and the bookmark advances. The writer does NOT raise."""
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.side_effect = UniqueViolationError("simulated triple collision")
    event = _stored("DistributionRegistered", _registered_payload())

    # Must NOT raise; writer-side swallow allows bookmark to advance.
    await proj.apply(event, conn)

    conn.execute.assert_awaited()


@pytest.mark.unit
async def test_unknown_event_type_falls_through() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("UnrelatedEvent", {})
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
def test_subscribed_event_types_carries_genesis_attestation_and_discard() -> None:
    """Shape pin: genesis + AttestationRecorded (Verified/Stale flip) +
    DistributionDiscarded (terminal Discard flip) are subscribed. The
    Verified / MarkedStale STREAM events are NOT subscribed (the
    Verified/Stale flip stays projection-only via AttestationRecorded)."""
    proj = DistributionSummaryProjection()
    assert "AttestationRecorded" in proj.subscribed_event_types
    assert "DistributionRegistered" in proj.subscribed_event_types
    assert "DistributionDiscarded" in proj.subscribed_event_types
    assert "DistributionVerified" not in proj.subscribed_event_types
    assert "DistributionMarkedStale" not in proj.subscribed_event_types


# ---------- DistributionDiscarded subscription (discard_distribution slice) ----------


def _discarded_payload() -> dict[str, Any]:
    return {
        "distribution_id": str(_DISTRIBUTION_ID),
        "reason": "bytes reclaimed from cold tier",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_REGISTERED_BY),
    }


@pytest.mark.unit
async def test_distribution_discarded_updates_status_to_discarded() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 1"
    event = _stored("DistributionDiscarded", _discarded_payload())
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_data_distribution_summary" in sql
    assert "'Discarded'" in sql
    # No `status != 'Discarded'` guard on the discard UPDATE: the row
    # must reach Discarded from any prior status.
    assert "status != 'Discarded'" not in sql
    assert args.args[1] == _DISTRIBUTION_ID


@pytest.mark.unit
async def test_distribution_discarded_rowcount_zero_logs_warning_does_not_raise() -> None:
    """When the target row is missing (projection lag) the writer must
    NOT raise; bookmark advances and next tick recovers."""
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 0"
    event = _stored("DistributionDiscarded", _discarded_payload())
    await proj.apply(event, conn)
    conn.execute.assert_awaited()


# ---------- AttestationRecorded subscription (Slice C extension) ----------


def _attestation_payload(
    *,
    distribution_id: UUID | None,
    kind: str = "ChecksumVerified",
    outcome: str = "Match",
    computed_value: str | None = "a" * 64,
) -> dict[str, Any]:
    return {
        "attestation_id": str(uuid4()),
        "dataset_id": str(_DATASET_ID),
        "distribution_id": str(distribution_id) if distribution_id is not None else None,
        "kind": kind,
        "outcome": outcome,
        "evidence": {
            "algorithm": "sha256",
            "value": computed_value,
            "verifier_supply_id": str(uuid4()),
            "verifier_kind": "HttpRangeChecksum",
        },
        "occurred_at": _NOW.isoformat(),
        "attested_by": str(_REGISTERED_BY),
    }


@pytest.mark.unit
async def test_attestation_match_updates_status_to_verified() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 1"
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(distribution_id=_DISTRIBUTION_ID, outcome="Match"),
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    sql = args.args[0]
    assert "UPDATE proj_data_distribution_summary" in sql
    assert args.args[1] == "Verified"
    assert args.args[2] == _DISTRIBUTION_ID


@pytest.mark.unit
async def test_attestation_mismatch_updates_status_to_stale() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 1"
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(
            distribution_id=_DISTRIBUTION_ID,
            outcome="Mismatch",
            computed_value="b" * 64,
        ),
    )
    await proj.apply(event, conn)
    args = conn.execute.await_args
    assert args is not None
    assert args.args[1] == "Stale"


@pytest.mark.unit
async def test_attestation_unreachable_does_not_update() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(
            distribution_id=_DISTRIBUTION_ID,
            outcome="Unreachable",
            computed_value=None,
        ),
    )
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_attestation_without_distribution_id_does_not_update() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(distribution_id=None),
    )
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_attestation_non_checksum_kind_does_not_update() -> None:
    """Kinds other than ChecksumVerified do not flip Distribution.status
    today (Slice C only wires the ChecksumVerified arm)."""
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(
            distribution_id=_DISTRIBUTION_ID,
            kind="BitRotChecked",
            outcome="Match",
        ),
    )
    await proj.apply(event, conn)
    conn.execute.assert_not_awaited()


@pytest.mark.unit
async def test_attestation_match_rowcount_zero_logs_warning_does_not_raise() -> None:
    """When the target Distribution row is missing (projection lag) the
    writer must NOT raise; bookmark advances and next tick recovers."""
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    conn.execute.return_value = "UPDATE 0"
    event = _stored(
        "AttestationRecorded",
        _attestation_payload(distribution_id=_DISTRIBUTION_ID, outcome="Match"),
    )
    # Must NOT raise.
    await proj.apply(event, conn)
    conn.execute.assert_awaited()


# Pin the distribution_id type asyncpg sees so a string-vs-UUID drift
# regression fails at the unit tier instead of slipping to integration.
@pytest.mark.unit
async def test_distribution_registered_passes_uuid_typed_ids() -> None:
    proj = DistributionSummaryProjection()
    conn = AsyncMock()
    event = _stored("DistributionRegistered", _registered_payload())

    await proj.apply(event, conn)

    args = conn.execute.await_args
    assert args is not None
    assert isinstance(args.args[1], UUID)
    assert isinstance(args.args[2], UUID)
    assert isinstance(args.args[3], UUID)
    assert isinstance(args.args[10], UUID)
