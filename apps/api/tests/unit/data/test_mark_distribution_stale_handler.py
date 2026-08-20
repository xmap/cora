"""Unit tests for the `mark_distribution_stale` application handler.

Update-style handler: loads the Distribution stream and appends
DistributionMarkedStale with optimistic concurrency. Unlike
discard_distribution, there is no parent-Dataset load and no
projection-backed sibling lookup: the decider has no cross-aggregate
guard, so the handler never touches Kernel.dataset_distribution_lookup.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.distribution import (
    DistributionCannotMarkStaleError,
    DistributionDiscarded,
    DistributionNotFoundError,
    DistributionRegistered,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.distribution.state import AccessProtocol
from cora.data.features import mark_distribution_stale
from cora.data.features.mark_distribution_stale import MarkDistributionStale
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000000f1")
_SUPPLY_A = UUID("01900000-0000-7000-8000-0000000000a1")
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-0000000000bb"))
_MARK_STALE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_distribution(
    store: InMemoryEventStore, *, distribution_id: UUID, supply_id: UUID
) -> None:
    event = DistributionRegistered(
        distribution_id=distribution_id,
        dataset_id=_DATASET_ID,
        supply_id=supply_id,
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=0,
        encoding=DatasetEncoding(media_type="application/x-hdf5", conforms_to=frozenset()),
        access_protocol=AccessProtocol.S3,
        occurred_at=_NOW,
        registered_by=_REGISTERED_BY,
    )
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDistribution",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


async def _seed_discarded(store: InMemoryEventStore, *, distribution_id: UUID) -> None:
    """Append a DistributionDiscarded directly onto an already-seeded
    Distribution stream, so the handler test can exercise the
    already-Discarded guard without going through discard_distribution's
    own cross-aggregate context."""
    discarded = DistributionDiscarded(
        distribution_id=distribution_id,
        reason="bytes reclaimed",
        occurred_at=_NOW,
        discarded_by=_REGISTERED_BY,
    )
    _, version = await store.load("Distribution", distribution_id)
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=version,
        events=[
            to_new_event(
                event_type=event_type_name(discarded),
                payload=to_payload(discarded),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DiscardDistribution",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_appends_marked_stale_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store)
    await mark_distribution_stale.bind(deps)(
        MarkDistributionStale(
            distribution_id=_DISTRIBUTION_ID,
            reason="  storage array declared dead by operations  ",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Distribution", _DISTRIBUTION_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "DistributionRegistered",
        "DistributionMarkedStale",
    ]
    marked_stale = events[1]
    assert marked_stale.event_id == _MARK_STALE_EVENT_ID
    assert marked_stale.metadata == {"command": "MarkDistributionStale"}
    assert marked_stale.payload == {
        "distribution_id": str(_DISTRIBUTION_ID),
        "reason": "storage array declared dead by operations",
        "trigger": "Operator",
        "occurred_at": _NOW.isoformat(),
        "marked_stale_by": str(_PRINCIPAL_ID),
    }


@pytest.mark.unit
async def test_handler_raises_not_found_when_distribution_missing() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(DistributionNotFoundError):
        await mark_distribution_stale.bind(deps)(
            MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_mark_stale_when_already_discarded() -> None:
    store = InMemoryEventStore()
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    await _seed_discarded(store, distribution_id=_DISTRIBUTION_ID)
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(DistributionCannotMarkStaleError):
        await mark_distribution_stale.bind(deps)(
            MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="too late"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_appends_marked_stale_again_when_already_stale() -> None:
    """Re-marking an already-Stale copy succeeds (not strict-not-idempotent)."""
    store = InMemoryEventStore()
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store)
    await mark_distribution_stale.bind(deps)(
        MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="first report"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    second_event_id = UUID("01900000-0000-7000-8000-00000000ee03")
    deps2 = build_deps(ids=[second_event_id], now=_NOW, event_store=store)
    await mark_distribution_stale.bind(deps2)(
        MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="second report"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Distribution", _DISTRIBUTION_ID)
    assert version == 3
    assert [e.event_type for e in events] == [
        "DistributionRegistered",
        "DistributionMarkedStale",
        "DistributionMarkedStale",
    ]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deny_deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await mark_distribution_stale.bind(deny_deps)(
            MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    store = InMemoryEventStore()
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW, event_store=store)
    await mark_distribution_stale.bind(deps)(
        MarkDistributionStale(distribution_id=_DISTRIBUTION_ID, reason="X"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Distribution", _DISTRIBUTION_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_data_includes_mark_distribution_stale() -> None:
    deps = build_deps(ids=[_MARK_STALE_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.mark_distribution_stale)
