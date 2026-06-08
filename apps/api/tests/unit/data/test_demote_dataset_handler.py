"""Unit tests for the `demote_dataset` application handler.

Update-style handler: load + fold + decide + append. NOT idempotency-
wrapped (strict-not-idempotent at decider). Mirrors discard_dataset /
promote_dataset handler shapes.

First concrete instantiation of the Q4 compensation-primitive pattern;
see [[project-dataset-demote-design]].
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetDemoted,
    DatasetPromoted,
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import demote_dataset
from cora.data.features.demote_dataset import DemoteDataset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000de01")
_DEMOTE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000de02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000de99")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000deaa")
_SEED_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000debb"))


async def _seed_registered(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    intent: str = "Trial",
) -> None:
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
        producing_run_end_state=None,
        intent=intent,
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


async def _seed_promoted(store: InMemoryEventStore, dataset_id: UUID) -> None:
    """Seed a Dataset already in Production intent (registered + promoted)."""
    await _seed_registered(store, dataset_id)
    promoted = DatasetPromoted(
        dataset_id=dataset_id,
        reason="initial promotion for tests",
        occurred_at=_NOW,
        promoted_by=_SEED_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(promoted),
        payload=to_payload(promoted),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="PromoteDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=1, events=[new_event]
    )


async def _seed_retracted(store: InMemoryEventStore, dataset_id: UUID) -> None:
    """Seed a Dataset already in Retracted intent (registered + promoted + demoted)."""
    await _seed_promoted(store, dataset_id)
    demoted = DatasetDemoted(
        dataset_id=dataset_id,
        reason="initial demote for tests",
        occurred_at=_NOW,
        demoted_by=_SEED_ACTOR_ID,
    )
    new_event = to_new_event(
        event_type=event_type_name(demoted),
        payload=to_payload(demoted),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DemoteDataset",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Dataset", stream_id=dataset_id, expected_version=2, events=[new_event]
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_promoted(store, _DATASET_ID)
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)
    result = await demote_dataset.bind(deps)(
        DemoteDataset(dataset_id=_DATASET_ID, reason="calibration error"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_dataset_demoted_with_correct_payload() -> None:
    store = InMemoryEventStore()
    await _seed_promoted(store, _DATASET_ID)
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)
    await demote_dataset.bind(deps)(
        DemoteDataset(dataset_id=_DATASET_ID, reason="  calibration error  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Dataset", _DATASET_ID)
    assert version == 3
    assert [e.event_type for e in events] == [
        "DatasetRegistered",
        "DatasetPromoted",
        "DatasetDemoted",
    ]
    demoted = events[2]
    assert demoted.event_id == _DEMOTE_EVENT_ID
    assert demoted.metadata == {"command": "DemoteDataset"}
    assert demoted.payload["dataset_id"] == str(_DATASET_ID)
    # Reason trimmed via DemotionReason VO.
    assert demoted.payload["reason"] == "calibration error"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_promoted(store, _DATASET_ID)
    deny_deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await demote_dataset.bind(deny_deps)(
            DemoteDataset(dataset_id=_DATASET_ID, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Stream untouched: only the seed events (register + promote).
    _, version = await store.load("Dataset", _DATASET_ID)
    assert version == 2


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-00000000debb")
    store = InMemoryEventStore()
    await _seed_promoted(store, _DATASET_ID)
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)
    await demote_dataset.bind(deps)(
        DemoteDataset(dataset_id=_DATASET_ID, reason="calibration error"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[2].causation_id == causation


@pytest.mark.unit
async def test_handler_raises_already_retracted_on_second_demote() -> None:
    """Strict-not-idempotent: second demote attempt rejects."""
    store = InMemoryEventStore()
    await _seed_retracted(store, _DATASET_ID)
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(DatasetAlreadyRetractedError):
        await demote_dataset.bind(deps)(
            DemoteDataset(dataset_id=_DATASET_ID, reason="trying again"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_demote_on_trial_dataset() -> None:
    """Trial→Retracted is semantically meaningless; handler surfaces
    the decider's rejection."""
    store = InMemoryEventStore()
    # Seed registered (default intent=Trial) but NOT promoted.
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(DatasetCannotDemoteError) as exc_info:
        await demote_dataset.bind(deps)(
            DemoteDataset(dataset_id=_DATASET_ID, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "Trial" in exc_info.value.reason


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_for_unknown_dataset() -> None:
    """Handler-level coverage of the empty-stream path: when no
    DatasetRegistered event exists for the target id, fold returns
    None, and the decider raises DatasetNotFoundError. Pinned at
    the handler boundary because this is the route → 404 path."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW, event_store=store)
    unknown_id = UUID("01900000-0000-7000-8000-00000000de99")
    with pytest.raises(DatasetNotFoundError):
        await demote_dataset.bind(deps)(
            DemoteDataset(dataset_id=unknown_id, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
def test_wire_data_includes_demote_dataset() -> None:
    deps = build_deps(ids=[_DEMOTE_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.demote_dataset)
