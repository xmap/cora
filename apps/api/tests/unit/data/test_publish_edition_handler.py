"""Unit tests for the `publish_edition` application handler.

Covers handler-level pre-load order: authz deny, EditionNotFound on
empty stream, the happy path (StubPersistentIdentifierMinter mint + StubEditionSerializer
re-serialize -> EditionPublished with the minted PID + re-serialized
published_content_hash), and the PersistentIdentifierMintError 502
propagation via an inline failing-mint stub.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.adapters.in_memory_distribution_lookup import (
    InMemoryDistributionLookup,
)
from cora.data.adapters.stub_edition_serializer import StubEditionSerializer
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
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
    EditionKind,
    EditionNotFoundError,
)
from cora.data.aggregates.edition.events import (
    EditionRegistered,
    EditionSealed,
)
from cora.data.aggregates.edition.events import (
    event_type_name as edition_event_type_name,
)
from cora.data.aggregates.edition.events import (
    to_payload as edition_to_payload,
)
from cora.data.features import publish_edition
from cora.data.features.publish_edition.command import PublishEdition
from cora.data.ports.distribution_lookup import CanonicalDistributionLookupResult
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.stub_persistent_identifier_minter import (
    StubPersistentIdentifierMinter,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identifier import (
    PersistentIdentifier,
    PersistentIdentifierScheme,
)
from cora.shared.identity import ActorId
from cora.shared.ports.persistent_identifier_minter import PersistentIdentifierMintError
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
_SEAL_HASH = "deadbeef" * 8
_PUBLISHED_HASH = "feedface" * 8


class FailingPersistentIdentifierMinter:
    """Mint arm always raises; tombstone arm is a no-op. Used to drive
    the publish handler's 502 PersistentIdentifierMintError path."""

    async def mint(
        self,
        *,
        scheme: PersistentIdentifierScheme,
        suffix: str | None,
    ) -> PersistentIdentifier:
        _ = suffix
        raise PersistentIdentifierMintError(scheme=scheme, reason="datacite down")

    async def tombstone(
        self,
        pid: PersistentIdentifier,
        reason: str,
    ) -> None:
        _ = (pid, reason)


async def _seed_dataset_production(
    store: InMemoryEventStore,
    dataset_id: UUID,
) -> None:
    registered = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
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


async def _seed_edition_sealed(
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
        publisher_facility_code="cora",
        publication_year=2026,
        license="CC-BY-4.0",
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    sealed = EditionSealed(
        edition_id=edition_id,
        content_hash=_SEAL_HASH,
        publisher_facility_code="cora",
        publication_year=2026,
        license="CC-BY-4.0",
        sealed_dataset_ids=dataset_ids,
        occurred_at=_NOW,
        sealed_by=ActorId(_PRINCIPAL_ID),
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
            to_new_event(
                event_type=edition_event_type_name(sealed),
                payload=edition_to_payload(sealed),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="SealEdition",
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


def _build_publish_deps(
    store: InMemoryEventStore,
    *,
    distribution_lookup: InMemoryDistributionLookup | None = None,
    serializer: object | None = None,
    minter: object | None = None,
    deny: bool = False,
) -> object:
    deps = build_deps(
        ids=[_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=deny,
    )
    from types import SimpleNamespace

    object.__setattr__(
        deps,
        "data",
        SimpleNamespace(
            distribution_lookup=distribution_lookup or _seeded_distribution_lookup(),
            edition_serializers={
                EditionKind.ROCRATE: serializer
                or StubEditionSerializer(content_hash=_PUBLISHED_HASH),
            },
            persistent_identifier_minter=minter or StubPersistentIdentifierMinter(),
        ),
    )
    return deps


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_emits_edition_published_on_happy_path() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_sealed(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_publish_deps(store)
    await publish_edition.bind(deps)(  # type: ignore[arg-type]
        PublishEdition(edition_id=_EDITION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 3
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionSealed",
        "EditionPublished",
    ]
    payload = events[2].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["external_pid_scheme"] == "DOI"
    assert payload["external_pid_value"].startswith("10.0000/cora-stub/")
    assert str(_EDITION_ID) in payload["external_pid_value"]
    assert payload["published_content_hash"] == _PUBLISHED_HASH
    assert payload["published_by"] == str(_PRINCIPAL_ID)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_sealed(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_publish_deps(store, deny=True)
    with pytest.raises(UnauthorizedError):
        await publish_edition.bind(deps)(  # type: ignore[arg-type]
            PublishEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Pre-load failures ----------


@pytest.mark.unit
async def test_handler_raises_edition_not_found_when_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = _build_publish_deps(store)
    with pytest.raises(EditionNotFoundError):
        await publish_edition.bind(deps)(  # type: ignore[arg-type]
            PublishEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Mint failure path ----------


@pytest.mark.unit
async def test_handler_propagates_persistent_identifier_mint_error() -> None:
    store = InMemoryEventStore()
    await _seed_dataset_production(store, _DATASET_ID)
    await _seed_edition_sealed(store, _EDITION_ID, dataset_ids=(_DATASET_ID,))
    deps = _build_publish_deps(store, minter=FailingPersistentIdentifierMinter())
    with pytest.raises(PersistentIdentifierMintError) as exc:
        await publish_edition.bind(deps)(  # type: ignore[arg-type]
            PublishEdition(edition_id=_EDITION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "datacite down" in exc.value.reason
    # No EditionPublished appended on mint failure.
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["EditionRegistered", "EditionSealed"]
