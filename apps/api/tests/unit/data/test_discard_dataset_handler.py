"""Unit tests for the `discard_dataset` application handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetCannotDiscardError,
    DatasetNotFoundError,
    InvalidDatasetDiscardReasonError,
)
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import discard_dataset
from cora.data.features.discard_dataset import DiscardDataset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-000000007b01")
_DISCARD_EVENT_ID = UUID("01900000-0000-7000-8000-000000007b02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-0000000000bb"))


async def _seed_registered(store: InMemoryEventStore, dataset_id: UUID) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=_SEED_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=0, events=[new_event]
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    result = await discard_dataset.bind(deps)(
        DiscardDataset(dataset_id=_DATASET_ID, reason="GDPR erasure"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_discarded_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    await discard_dataset.bind(deps)(
        DiscardDataset(dataset_id=_DATASET_ID, reason="  bytes purged from S3 per request  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Dataset", _DATASET_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["DatasetRegistered", "DatasetDiscarded"]
    discarded = events[1]
    assert discarded.event_id == _DISCARD_EVENT_ID
    assert discarded.metadata == {"command": "DiscardDataset"}
    assert discarded.payload == {
        "dataset_id": str(_DATASET_ID),
        "reason": "bytes purged from S3 per request",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_PRINCIPAL_ID),
    }


@pytest.mark.unit
async def test_handler_raises_not_found_when_dataset_missing() -> None:
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW)
    with pytest.raises(DatasetNotFoundError):
        await discard_dataset.bind(deps)(
            DiscardDataset(dataset_id=_DATASET_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_reason_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(InvalidDatasetDiscardReasonError):
        await discard_dataset.bind(deps)(
            DiscardDataset(dataset_id=_DATASET_ID, reason="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_discard_when_already_discarded() -> None:
    """Strict-not-idempotent: re-discarding raises."""
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    await discard_dataset.bind(deps)(
        DiscardDataset(dataset_id=_DATASET_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second call needs a fresh ID so the deps' id_generator
    # doesn't run dry; rebuild deps for the retry.
    deps2 = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(DatasetCannotDiscardError):
        await discard_dataset.bind(deps2)(
            DiscardDataset(dataset_id=_DATASET_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deny_deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await discard_dataset.bind(deny_deps)(
            DiscardDataset(dataset_id=_DATASET_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    await discard_dataset.bind(deps)(
        DiscardDataset(dataset_id=_DATASET_ID, reason="X"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_data_includes_discard_dataset() -> None:
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.discard_dataset)
