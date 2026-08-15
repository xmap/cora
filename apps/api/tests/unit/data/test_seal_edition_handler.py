"""Unit tests for the `seal_edition` application handler.

Covers handler-level pre-load order: authz, EditionNotFound,
DatasetNotFound, FacilityLookup miss, serializer raise, distribution
miss, and the happy path that emits `EditionSealed`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.adapters.stub_edition_serializer import (
    FailingEditionSerializer,
)
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetPromoted,
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import (
    event_type_name as dataset_event_type_name,
)
from cora.data.aggregates.dataset.events import (
    to_payload as dataset_to_payload,
)
from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
)
from cora.data.aggregates.distribution.state import (
    DistributionStatus,
    DistributionUri,
)
from cora.data.aggregates.edition import (
    EditionDatasetDistributionNotFoundError,
    EditionKind,
    EditionNotFoundError,
    EditionPublisherNotFoundError,
    EditionSerializerError,
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
from cora.data.features import seal_edition
from cora.data.features.seal_edition.command import SealEdition
from cora.data.ports.distribution_lookup import CanonicalDistributionLookupResult
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000eda1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da99")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-00000000ad99")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000000eee")


async def _seed_dataset_production(
    store: InMemoryEventStore,
    dataset_id: UUID,
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
    promoted = DatasetPromoted(
        dataset_id=dataset_id,
        reason="for publication",
        occurred_at=_NOW,
        promoted_by=ActorId(_PRINCIPAL_ID),
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
            ),
            to_new_event(
                event_type=dataset_event_type_name(promoted),
                payload=dataset_to_payload(promoted),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="PromoteDataset",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            ),
        ],
    )


async def _seed_edition_registered(
    store: InMemoryEventStore,
    edition_id: UUID,
    *,
    dataset_ids: tuple[UUID, ...],
    publisher_facility_code: str | None = "cora",
    license: str | None = "CC-BY-4.0",
    publication_year: int | None = 2026,
) -> None:
    registered = EditionRegistered(
        edition_id=edition_id,
        kind="ROCrate",
        title="Pilot",
        dataset_ids=dataset_ids,
        creators=({"actor_id": ActorId(_ACTOR_ID), "affiliation": "ANL"},),
        publisher_facility_code=publisher_facility_code,
        publication_year=publication_year,
        license=license,
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
            ),
        ],
    )


def _seeded_distribution_lookup() -> InMemoryDistributionLookup:
    lookup = InMemoryDistributionLookup()
    lookup.register(
        CanonicalDistributionLookupResult(
            distribution_id=_DISTRIBUTION_ID,
            dataset_id=_DATASET_ID,
            uri=DistributionUri("s3://bucket/k"),
            checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
            byte_size=1024,
            encoding=DatasetEncoding(media_type="application/x-hdf5"),
            status=DistributionStatus.REGISTERED,
        )
    )
    return lookup


def _build_seal_deps(
    store: InMemoryEventStore,
    *,
    distribution_lookup: InMemoryDistributionLookup | None = None,
    serializer: object | None = None,
    facility_lookup: InMemoryFacilityLookup | None = None,
    deny: bool = False,
) -> object:
    deps = build_deps(
        ids=[_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=deny,
        facility_lookup=facility_lookup,
    )
    from types import SimpleNamespace

    object.__setattr__(
        deps,
        "data",
        SimpleNamespace(
            distribution_lookup=distribution_lookup or _seeded_distribution_lookup(),
            edition_serializers={
                EditionKind.ROCRATE: serializer or RoCrate12Adapter(),
            },
        ),
    )
    return deps


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_emits_edition_sealed_on_happy_path() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_seal_deps(store)
    await seal_edition.bind(deps)(  # type: ignore[arg-type]
        SealEdition(edition_id=_EDITION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["EditionRegistered", "EditionSealed"]
    payload = events[1].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["publisher_facility_code"] == "cora"
    assert payload["publication_year"] == 2026
    assert payload["license"] == "CC-BY-4.0"
    assert payload["sealed_dataset_ids"] == [str(_DATASET_ID)]
    assert len(payload["content_hash"]) == 64


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_seal_deps(store, deny=True)
    with pytest.raises(UnauthorizedError):
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Pre-load failures ----------


@pytest.mark.unit
async def test_handler_raises_edition_not_found_when_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = _build_seal_deps(store)
    with pytest.raises(EditionNotFoundError):
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_member_missing() -> None:
    store = InMemoryEventStore()
    await _seed_edition_registered(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_seal_deps(store)
    with pytest.raises(DatasetNotFoundError):
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_publisher_facility_unknown() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(
        store,
        _EDITION_ID,
        dataset_ids=(_DATASET_ID,),
        publisher_facility_code="unknown",
    )
    deps = _build_seal_deps(store)
    with pytest.raises(EditionPublisherNotFoundError) as exc:
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.facility_code == "unknown"


@pytest.mark.unit
async def test_handler_raises_when_no_publisher_supplied() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(
        store,
        _EDITION_ID,
        dataset_ids=(_DATASET_ID,),
        publisher_facility_code=None,
    )
    deps = _build_seal_deps(store)
    with pytest.raises(EditionPublisherNotFoundError):
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_when_canonical_distribution_missing() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    # Empty distribution lookup -> no canonical row for the Dataset
    deps = _build_seal_deps(store, distribution_lookup=InMemoryDistributionLookup())
    with pytest.raises(EditionDatasetDistributionNotFoundError):
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Serializer failure path ----------


@pytest.mark.unit
async def test_handler_wraps_serializer_failure_as_edition_serializer_error() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    failing = FailingEditionSerializer(RuntimeError("boom"))
    deps = _build_seal_deps(store, serializer=failing)
    with pytest.raises(EditionSerializerError) as exc:
        await seal_edition.bind(deps)(  # type: ignore[arg-type]
            SealEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "boom" in exc.value.reason


# ---------- Override paths ----------


@pytest.mark.unit
async def test_handler_uses_publication_year_override() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(
        store, _EDITION_ID, dataset_ids=(_DATASET_ID,), publication_year=None
    )
    deps = _build_seal_deps(store)
    await seal_edition.bind(deps)(  # type: ignore[arg-type]
        SealEdition(edition_id=_EDITION_ID, publication_year_override=2025),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Edition", _EDITION_ID)
    assert events[1].payload["publication_year"] == 2025


@pytest.mark.unit
async def test_handler_uses_publisher_facility_code_override() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_registered(
        store,
        _EDITION_ID,
        dataset_ids=(_DATASET_ID,),
        publisher_facility_code=None,
    )
    facility_lookup = InMemoryFacilityLookup()
    facility_lookup.register(
        facility_id=UUID("01900000-0000-7000-8000-00000000c08a"),
        code=FacilityCode("aps"),
        kind="Site",
        status="Active",
    )
    deps = _build_seal_deps(store, facility_lookup=facility_lookup)
    await seal_edition.bind(deps)(  # type: ignore[arg-type]
        SealEdition(edition_id=_EDITION_ID, publisher_facility_code="aps"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Edition", _EDITION_ID)
    assert events[1].payload["publisher_facility_code"] == "aps"
