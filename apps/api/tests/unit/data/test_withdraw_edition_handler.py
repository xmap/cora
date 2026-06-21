"""Unit tests for the `withdraw_edition` application handler.

Covers handler-level pre-load order: authz deny, EditionNotFound on
empty stream, the cheap status guard (EditionCannotWithdrawError on a
non-Published Edition), the happy path (StubPersistentIdentifierMinter.tombstone no-op
-> EditionWithdrawn), and the PersistentIdentifierMinterTombstoneError 502 propagation
via an inline failing-tombstone stub.

The defensive `EditionWithdrawnWithoutPersistentIdError` branch is not
exercised here: a Published Edition folded from its event stream always
carries an external_pid (the evolver reconstructs it from the
EditionPublished payload, whose value the PersistentIdentifier VO
requires to be non-empty). The branch is unreachable without a corrupt
stream, which the handler test cannot inject because it folds state
from the store rather than constructing it directly.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import UnauthorizedError
from cora.data.aggregates.edition import (
    EditionCannotWithdrawError,
    EditionNotFoundError,
    PersistentIdentifierMinterTombstoneError,
)
from cora.data.aggregates.edition.events import (
    EditionPublished,
    EditionRegistered,
    EditionSealed,
)
from cora.data.aggregates.edition.events import (
    event_type_name as edition_event_type_name,
)
from cora.data.aggregates.edition.events import (
    to_payload as edition_to_payload,
)
from cora.data.features import withdraw_edition
from cora.data.features.withdraw_edition.command import WithdrawEdition
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
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000eda1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da99")
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000ac70")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000000eee")
_SEAL_HASH = "deadbeef" * 8
_PUBLISHED_HASH = "feedface" * 8
_PID_VALUE = "10.0000/cora-stub/published-edition"


class FailingTombstonePersistentIdentifierMinter:
    """Tombstone arm always raises; mint arm is unused. Drives the
    withdraw handler's 502 PersistentIdentifierMinterTombstoneError path."""

    async def mint(
        self,
        *,
        scheme: PersistentIdentifierScheme,
        suffix: str | None,
    ) -> PersistentIdentifier:
        _ = suffix
        return PersistentIdentifier(scheme=scheme, value="10.0/unused")

    async def tombstone(
        self,
        pid: PersistentIdentifier,
        reason: str,
    ) -> None:
        _ = reason
        raise PersistentIdentifierMinterTombstoneError(
            persistent_id_value=pid.value,
            reason="datacite tombstone unreachable",
        )


async def _seed_edition_published(
    store: InMemoryEventStore,
    edition_id: UUID,
) -> None:
    registered = EditionRegistered(
        edition_id=edition_id,
        kind="ROCrate",
        title="Pilot",
        dataset_ids=(_DATASET_ID,),
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
        sealed_dataset_ids=(_DATASET_ID,),
        occurred_at=_NOW,
        sealed_by=ActorId(_PRINCIPAL_ID),
    )
    published = EditionPublished(
        edition_id=edition_id,
        external_pid_scheme="DOI",
        external_pid_value=_PID_VALUE,
        published_content_hash=_PUBLISHED_HASH,
        occurred_at=_NOW,
        published_by=ActorId(_PRINCIPAL_ID),
    )
    events = [registered, sealed, published]
    await store.append(
        stream_type="Edition",
        stream_id=edition_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=edition_event_type_name(event),
                payload=edition_to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="SeedEdition",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for event in events
        ],
    )


async def _seed_edition_sealed(
    store: InMemoryEventStore,
    edition_id: UUID,
) -> None:
    registered = EditionRegistered(
        edition_id=edition_id,
        kind="ROCrate",
        title="Pilot",
        dataset_ids=(_DATASET_ID,),
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
        sealed_dataset_ids=(_DATASET_ID,),
        occurred_at=_NOW,
        sealed_by=ActorId(_PRINCIPAL_ID),
    )
    await store.append(
        stream_type="Edition",
        stream_id=edition_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=edition_event_type_name(event),
                payload=edition_to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="SeedEdition",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
            for event in (registered, sealed)
        ],
    )


def _build_withdraw_deps(
    store: InMemoryEventStore,
    *,
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
        SimpleNamespace(persistent_identifier_minter=minter or StubPersistentIdentifierMinter()),
    )
    return deps


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_emits_edition_withdrawn_on_happy_path() -> None:
    store = InMemoryEventStore()
    await _seed_edition_published(store, _EDITION_ID)
    deps = _build_withdraw_deps(store)
    await withdraw_edition.bind(deps)(  # type: ignore[arg-type]
        WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason="superseded by v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 4
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionSealed",
        "EditionPublished",
        "EditionWithdrawn",
    ]
    payload = events[3].payload
    assert payload["edition_id"] == str(_EDITION_ID)
    assert payload["withdrawal_reason"] == "superseded by v2"
    assert payload["withdrawn_by"] == str(_PRINCIPAL_ID)


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_edition_published(store, _EDITION_ID)
    deps = _build_withdraw_deps(store, deny=True)
    with pytest.raises(UnauthorizedError):
        await withdraw_edition.bind(deps)(  # type: ignore[arg-type]
            WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Pre-load failures ----------


@pytest.mark.unit
async def test_handler_raises_edition_not_found_when_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = _build_withdraw_deps(store)
    with pytest.raises(EditionNotFoundError):
        await withdraw_edition.bind(deps)(  # type: ignore[arg-type]
            WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_withdraw_when_not_published() -> None:
    store = InMemoryEventStore()
    await _seed_edition_sealed(store, _EDITION_ID)
    deps = _build_withdraw_deps(store)
    with pytest.raises(EditionCannotWithdrawError):
        await withdraw_edition.bind(deps)(  # type: ignore[arg-type]
            WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Tombstone failure path ----------


@pytest.mark.unit
async def test_handler_propagates_tombstone_error() -> None:
    store = InMemoryEventStore()
    await _seed_edition_published(store, _EDITION_ID)
    deps = _build_withdraw_deps(store, minter=FailingTombstonePersistentIdentifierMinter())
    with pytest.raises(PersistentIdentifierMinterTombstoneError) as exc:
        await withdraw_edition.bind(deps)(  # type: ignore[arg-type]
            WithdrawEdition(edition_id=_EDITION_ID, withdrawal_reason="x"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.persistent_id_value == _PID_VALUE
    # No EditionWithdrawn appended when the tombstone wire fails.
    events, version = await store.load("Edition", _EDITION_ID)
    assert version == 3
    assert [e.event_type for e in events] == [
        "EditionRegistered",
        "EditionSealed",
        "EditionPublished",
    ]
