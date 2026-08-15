"""Unit tests for the `add_dataset_to_edition` application handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import (
    event_type_name as dataset_event_type_name,
)
from cora.data.aggregates.dataset.events import (
    to_payload as dataset_to_payload,
)
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.edition import (
    EditionCannotBindToDiscardedDatasetError,
    EditionDatasetAlreadyMemberError,
    EditionNotFoundError,
)
from cora.data.aggregates.edition.events import (
    EditionRegistered,
)
from cora.data.aggregates.edition.events import (
    event_type_name as edition_event_type_name,
)
from cora.data.aggregates.edition.events import (
    to_payload as edition_to_payload,
)
from cora.data.features import add_dataset_to_edition
from cora.data.features.add_dataset_to_edition import AddDatasetToEdition
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-000000ed1a01")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000ed1a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID_INITIAL = UUID("01900000-0000-7000-8000-00000000da01")
_DATASET_ID_NEW = UUID("01900000-0000-7000-8000-00000000da02")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")


async def _seed_dataset(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    discarded: bool = False,
) -> None:
    from cora.data.aggregates.dataset.events import DatasetDiscarded

    registered = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=1024,
        encoding=DatasetEncoding(media_type="application/x-hdf5", conforms_to=frozenset()),
        producing_run_id=None,
        subject_id=None,
        derived_from=frozenset(),
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    await store.append(
        stream_type="Dataset",
        stream_id=dataset_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=dataset_event_type_name(registered),
                payload=dataset_to_payload(registered),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDataset",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    if discarded:
        discarded_evt = DatasetDiscarded(
            dataset_id=dataset_id,
            reason="bytes-deleted",
            occurred_at=_NOW,
            discarded_by=ActorId(_PRINCIPAL_ID),
        )
        await store.append(
            stream_type="Dataset",
            stream_id=dataset_id,
            expected_version=1,
            events=[
                to_new_event(
                    event_type=dataset_event_type_name(discarded_evt),
                    payload=dataset_to_payload(discarded_evt),
                    occurred_at=_NOW,
                    event_id=uuid4(),
                    command_name="DiscardDataset",
                    correlation_id=_CORRELATION_ID,
                    principal_id=_PRINCIPAL_ID,
                )
            ],
        )


async def _seed_edition(
    store: InMemoryEventStore,
    edition_id: UUID,
    *,
    dataset_ids: tuple[UUID, ...],
) -> None:
    registered = EditionRegistered(
        edition_id=edition_id,
        kind="ROCrate",
        title="Pilot",
        dataset_ids=dataset_ids,
        creators=({"actor_id": ActorId(_ACTOR_ID), "affiliation": "ANL"},),
        publisher_facility_code=None,
        publication_year=None,
        license=None,
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    await store.append(
        stream_type="Edition",
        stream_id=edition_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=edition_event_type_name(registered),
                payload=edition_to_payload(registered),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterEdition",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_appends_dataset_added_event_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_INITIAL)
    await _seed_dataset(store, _DATASET_ID_NEW)
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_INITIAL,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    await add_dataset_to_edition.bind(deps)(
        AddDatasetToEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_NEW),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionDatasetAdded",
    ]
    payload = events[1].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["dataset_id"] == str(_DATASET_ID_NEW)
    assert payload["added_by"] == str(_PRINCIPAL_ID)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_INITIAL)
    await _seed_dataset(store, _DATASET_ID_NEW)
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_INITIAL,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await add_dataset_to_edition.bind(deps)(
            AddDatasetToEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_NEW),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Pre-load failures ----------


@pytest.mark.unit
async def test_handler_raises_edition_not_found_when_stream_empty() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_NEW)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    missing_edition = uuid4()
    with pytest.raises(EditionNotFoundError):
        await add_dataset_to_edition.bind(deps)(
            AddDatasetToEdition(edition_id=missing_edition, dataset_id=_DATASET_ID_NEW),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_peer_missing() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_INITIAL)
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_INITIAL,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    missing_ds = uuid4()
    with pytest.raises(DatasetNotFoundError):
        await add_dataset_to_edition.bind(deps)(
            AddDatasetToEdition(edition_id=_EDITION_ID, dataset_id=missing_ds),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Decider rejections via handler ----------


@pytest.mark.unit
async def test_handler_raises_when_dataset_already_member() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_INITIAL)
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_INITIAL,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionDatasetAlreadyMemberError):
        await add_dataset_to_edition.bind(deps)(
            AddDatasetToEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_INITIAL),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_dataset_discarded() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID_INITIAL)
    await _seed_dataset(store, _DATASET_ID_NEW, discarded=True)
    await _seed_edition(store, _EDITION_ID, dataset_ids=(_DATASET_ID_INITIAL,))
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionCannotBindToDiscardedDatasetError):
        await add_dataset_to_edition.bind(deps)(
            AddDatasetToEdition(edition_id=_EDITION_ID, dataset_id=_DATASET_ID_NEW),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
