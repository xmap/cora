"""Unit tests for Distribution events + evolver, focused on the
DistributionMarkedStale and DistributionDiscarded transitions.

Covers the to_payload / from_stored round-trip for each, the Malformed
wrap on a corrupt payload, and the evolver fold-symmetry (a
[Registered, MarkedStale] fold lands status=STALE + the mark-stale
attribution fields; a [Registered, Discarded] fold lands
status=DISCARDED + the discard attribution fields; both preserve every
genesis field).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.distribution import (
    DistributionDiscarded,
    DistributionMarkedStale,
    DistributionRegistered,
    DistributionStatus,
    TriggerSource,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.data.aggregates.distribution.state import AccessProtocol
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000000f1")
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-0000000000a1")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000088"))
_MARKED_STALE_BY = ActorId(UUID("01900000-0000-7000-8000-000000000098"))
_DISCARDED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000099"))


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=2,
        event_id=uuid4(),
        stream_type="Distribution",
        stream_id=_DISTRIBUTION_ID,
        version=2,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


def _registered() -> DistributionRegistered:
    return DistributionRegistered(
        distribution_id=_DISTRIBUTION_ID,
        dataset_id=_DATASET_ID,
        supply_id=_SUPPLY_ID,
        uri="s3://bucket/key.h5",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        ),
        access_protocol=AccessProtocol.S3,
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )


def _marked_stale() -> DistributionMarkedStale:
    return DistributionMarkedStale(
        distribution_id=_DISTRIBUTION_ID,
        reason="storage array declared dead by operations",
        trigger=TriggerSource.OPERATOR.value,
        occurred_at=_NOW,
        marked_stale_by=_MARKED_STALE_BY,
    )


def _discarded() -> DistributionDiscarded:
    return DistributionDiscarded(
        distribution_id=_DISTRIBUTION_ID,
        reason="bytes reclaimed from cold tier",
        occurred_at=_NOW,
        discarded_by=_DISCARDED_BY,
    )


@pytest.mark.unit
def test_distribution_marked_stale_event_type_name() -> None:
    assert event_type_name(_marked_stale()) == "DistributionMarkedStale"


@pytest.mark.unit
def test_distribution_marked_stale_to_payload_shape() -> None:
    assert to_payload(_marked_stale()) == {
        "distribution_id": str(_DISTRIBUTION_ID),
        "reason": "storage array declared dead by operations",
        "trigger": "Operator",
        "occurred_at": _NOW.isoformat(),
        "marked_stale_by": str(_MARKED_STALE_BY),
    }


@pytest.mark.unit
def test_distribution_marked_stale_round_trip() -> None:
    event = _marked_stale()
    stored = _stored("DistributionMarkedStale", to_payload(event))
    assert from_stored(stored) == event


@pytest.mark.unit
def test_distribution_marked_stale_malformed_payload_raises() -> None:
    """A payload missing the required `reason` key surfaces as a
    MalformedDistributionMarkedStale via deserialize_or_raise."""
    bad = _stored(
        "DistributionMarkedStale",
        {
            "distribution_id": str(_DISTRIBUTION_ID),
            "occurred_at": _NOW.isoformat(),
            "marked_stale_by": str(_MARKED_STALE_BY),
        },
    )
    with pytest.raises(Exception, match="Malformed DistributionMarkedStale"):
        from_stored(bad)


@pytest.mark.unit
def test_fold_registered_then_marked_stale_sets_stale_status_and_preserves_genesis() -> None:
    state = fold([_registered(), _marked_stale()])
    assert state is not None
    assert state.status is DistributionStatus.STALE
    assert state.marked_stale_at == _NOW
    assert state.marked_stale_by == _MARKED_STALE_BY
    # Genesis fields preserved across the transition.
    assert state.id == _DISTRIBUTION_ID
    assert state.dataset_id == _DATASET_ID
    assert state.supply_id == _SUPPLY_ID
    assert state.uri.value == "s3://bucket/key.h5"
    assert state.checksum.value == _GOOD_SHA256
    assert state.byte_size == 1024
    assert state.encoding.media_type == "application/x-hdf5"
    assert state.access_protocol.value == "S3"
    assert state.registered_at == _NOW
    assert state.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_fold_marked_stale_on_empty_stream_raises() -> None:
    """A DistributionMarkedStale with no prior genesis event is a
    malformed stream; the evolver's require_state guard raises."""
    with pytest.raises(ValueError, match="DistributionMarkedStale"):
        fold([_marked_stale()])


@pytest.mark.unit
def test_fold_registered_marked_stale_then_discarded_does_not_resurrect_stale() -> None:
    """A [Registered, MarkedStale, Discarded] fold lands on DISCARDED
    (terminal), not STALE: the aggregate's own fold-order has no
    resurrection concern the way the projection UPDATE guard does, but
    this pins that the final status still reflects the last event."""
    state = fold([_registered(), _marked_stale(), _discarded()])
    assert state is not None
    assert state.status is DistributionStatus.DISCARDED
    assert state.marked_stale_at == _NOW
    assert state.marked_stale_by == _MARKED_STALE_BY
    assert state.discarded_at == _NOW
    assert state.discarded_by == _DISCARDED_BY


@pytest.mark.unit
def test_distribution_discarded_event_type_name() -> None:
    assert event_type_name(_discarded()) == "DistributionDiscarded"


@pytest.mark.unit
def test_distribution_discarded_to_payload_shape() -> None:
    assert to_payload(_discarded()) == {
        "distribution_id": str(_DISTRIBUTION_ID),
        "reason": "bytes reclaimed from cold tier",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_DISCARDED_BY),
    }


@pytest.mark.unit
def test_distribution_discarded_round_trip() -> None:
    event = _discarded()
    stored = _stored("DistributionDiscarded", to_payload(event))
    assert from_stored(stored) == event


@pytest.mark.unit
def test_distribution_discarded_malformed_payload_raises() -> None:
    """A payload missing the required `reason` key surfaces as a
    MalformedDistributionDiscarded via deserialize_or_raise."""
    bad = _stored(
        "DistributionDiscarded",
        {
            "distribution_id": str(_DISTRIBUTION_ID),
            "occurred_at": _NOW.isoformat(),
            "discarded_by": str(_DISCARDED_BY),
        },
    )
    with pytest.raises(Exception, match="Malformed DistributionDiscarded"):
        from_stored(bad)


@pytest.mark.unit
def test_fold_registered_then_discarded_sets_discarded_status_and_preserves_genesis() -> None:
    state = fold([_registered(), _discarded()])
    assert state is not None
    assert state.status is DistributionStatus.DISCARDED
    assert state.discarded_at == _NOW
    assert state.discarded_by == _DISCARDED_BY
    assert state.discard_reason == "bytes reclaimed from cold tier"
    # Genesis fields preserved across the transition.
    assert state.id == _DISTRIBUTION_ID
    assert state.dataset_id == _DATASET_ID
    assert state.supply_id == _SUPPLY_ID
    assert state.uri.value == "s3://bucket/key.h5"
    assert state.checksum.value == _GOOD_SHA256
    assert state.byte_size == 1024
    assert state.encoding.media_type == "application/x-hdf5"
    assert state.access_protocol.value == "S3"
    assert state.registered_at == _NOW
    assert state.registered_by == _REGISTERED_BY


@pytest.mark.unit
def test_fold_discarded_on_empty_stream_raises() -> None:
    """A DistributionDiscarded with no prior genesis event is a malformed
    stream; the evolver's require_state guard raises."""
    with pytest.raises(ValueError, match="DistributionDiscarded"):
        fold([_discarded()])
