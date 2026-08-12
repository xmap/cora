"""Unit tests for the `register_edition` application handler.

Mirror of `register_distribution` handler test shape: pre-loads each
member Dataset; authz called; missing Dataset surfaces as
DatasetNotFoundError; bind-on-Discarded surfaces as
EditionCannotBindToDiscardedDatasetError.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetDiscarded,
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.dataset.state import DatasetChecksum, DatasetEncoding
from cora.data.aggregates.edition import EditionCannotBindToDiscardedDatasetError
from cora.data.features import register_edition
from cora.data.features.register_edition import CreatorEntry, RegisterEdition
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-000000ed1701")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000ed1702")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")


def _good_command(**overrides: object) -> RegisterEdition:
    base: dict[str, object] = {
        "kind": "ROCrate",
        "title": "Pilot Edition",
        "dataset_ids": frozenset({_DATASET_ID}),
        "creators": (CreatorEntry(actor_id=_ACTOR_ID, affiliation="ANL"),),
        "license": None,
        "publication_year": None,
        "publisher_facility_code": None,
    }
    base.update(overrides)
    return RegisterEdition(**base)  # type: ignore[arg-type]


async def _seed_dataset(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    discarded: bool = False,
) -> None:
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
    events = [
        to_new_event(
            event_type=event_type_name(registered),
            payload=to_payload(registered),
            occurred_at=_NOW,
            event_id=uuid4(),
            command_name="RegisterDataset",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
    ]
    await store.append(
        stream_type="Dataset",
        stream_id=dataset_id,
        expected_version=0,
        events=events,
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
                    event_type=event_type_name(discarded_evt),
                    payload=to_payload(discarded_evt),
                    occurred_at=_NOW,
                    event_id=uuid4(),
                    command_name="DiscardDataset",
                    correlation_id=_CORRELATION_ID,
                    principal_id=_PRINCIPAL_ID,
                )
            ],
        )


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_new_edition_id_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = build_deps(ids=[_EDITION_ID, _EVENT_ID], now=_NOW, event_store=store)
    edition_id = await register_edition.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert edition_id == _EDITION_ID


@pytest.mark.unit
async def test_handler_appends_edition_registered_event_with_canonical_payload() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = build_deps(ids=[_EDITION_ID, _EVENT_ID], now=_NOW, event_store=store)
    await register_edition.bind(deps)(
        _good_command(license="CC-BY-4.0", publication_year=2024),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["EditionRegistered"]
    payload = events[0].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["kind"] == "ROCrate"
    assert payload["title"] == "Pilot Edition"
    assert payload["dataset_ids"] == [str(_DATASET_ID)]
    assert payload["license"] == "CC-BY-4.0"
    assert payload["publication_year"] == 2024
    assert payload["registered_by"] == str(_PRINCIPAL_ID)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    deps = build_deps(
        ids=[_EDITION_ID, _EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError) as exc:
        await register_edition.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.reason == "denied for test"
    events, _ = await store.load("Edition", _EDITION_ID)
    assert events == []


# ---------- Cross-aggregate ----------


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_member_missing() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_EDITION_ID, _EVENT_ID], now=_NOW, event_store=store)
    missing = uuid4()
    with pytest.raises(DatasetNotFoundError):
        await register_edition.bind(deps)(
            _good_command(dataset_ids=frozenset({missing})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_on_discarded_member_dataset() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID, discarded=True)
    deps = build_deps(ids=[_EDITION_ID, _EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(EditionCannotBindToDiscardedDatasetError) as exc:
        await register_edition.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.dataset_id == _DATASET_ID


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_data_includes_register_edition() -> None:
    deps = build_deps(ids=[_EDITION_ID, _EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.register_edition)
