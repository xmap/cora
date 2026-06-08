"""Unit tests for the `get_dataset` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
)
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import get_dataset
from cora.data.features.get_dataset import GetDataset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-0000000000bb"))


async def _seed_dataset(store: InMemoryEventStore, dataset_id: UUID) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="32-ID FlyScan recon",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1024,
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
async def test_handler_returns_dataset_when_present() -> None:
    store = InMemoryEventStore()
    dataset_id = uuid4()
    await _seed_dataset(store, dataset_id)
    deps = build_deps(ids=[uuid4()], now=_NOW, event_store=store)
    result = await get_dataset.bind(deps)(
        GetDataset(dataset_id=dataset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == dataset_id
    assert result.name.value == "32-ID FlyScan recon"
    assert result.uri.value == "s3://b/k"
    assert result.byte_size == 1024


@pytest.mark.unit
async def test_handler_returns_none_when_dataset_does_not_exist() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW)
    result = await get_dataset.bind(deps)(
        GetDataset(dataset_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[uuid4()], now=_NOW, deny=True)
    with pytest.raises(UnauthorizedError):
        await get_dataset.bind(deps)(
            GetDataset(dataset_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
