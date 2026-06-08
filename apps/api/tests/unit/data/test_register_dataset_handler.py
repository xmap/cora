"""Unit tests for the `register_dataset` application handler.

Mirror of register_subject + start_run handler tests: VOs validated,
authz called, idempotency-not-tested (that's the wire decorator),
cross-aggregate context loaded from real in-memory event store.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DerivedFromDatasetsNotFoundError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import register_dataset
from cora.data.features.register_dataset import RegisterDataset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run.events import (
    RunStarted,
)
from cora.run.aggregates.run.events import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run.events import (
    to_payload as run_to_payload,
)
from cora.subject.aggregates.subject.events import (
    SubjectRegistered,
)
from cora.subject.aggregates.subject.events import (
    event_type_name as subject_event_type_name,
)
from cora.subject.aggregates.subject.events import (
    to_payload as subject_to_payload,
)
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-000000007a01")
_REG_EVENT_ID = UUID("01900000-0000-7000-8000-000000007a02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _good_command(**overrides: object) -> RegisterDataset:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "producing_run_id": None,
        "subject_id": None,
        "derived_from": frozenset[UUID](),
    }
    base.update(overrides)
    return RegisterDataset(**base)  # type: ignore[arg-type]


async def _seed_run(store: InMemoryEventStore, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="seed-run",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(event),
        payload=run_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event])


async def _seed_subject(store: InMemoryEventStore, subject_id: UUID) -> None:
    from cora.shared.identity import ActorId

    event = SubjectRegistered(
        subject_id=subject_id,
        name="seed-subject",
        occurred_at=_NOW,
        registered_by=ActorId(_PRINCIPAL_ID),
    )
    new_event = to_new_event(
        event_type=subject_event_type_name(event),
        payload=subject_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterSubject",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Subject", stream_id=subject_id, expected_version=0, events=[new_event]
    )


async def _seed_dataset(store: InMemoryEventStore, dataset_id: UUID) -> None:
    from cora.shared.identity import ActorId

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
        registered_by=ActorId(_PRINCIPAL_ID),
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


# ---------- Happy path ----------


@pytest.mark.unit
async def test_handler_returns_new_dataset_id_on_success() -> None:
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW)
    dataset_id = await register_dataset.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert dataset_id == _DATASET_ID


@pytest.mark.unit
async def test_handler_appends_dataset_registered_event_with_canonical_payload() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_dataset.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Dataset", _DATASET_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["DatasetRegistered"]
    registered = events[0]
    assert registered.event_id == _REG_EVENT_ID
    assert registered.metadata == {"command": "RegisterDataset"}
    assert registered.payload["dataset_id"] == str(_DATASET_ID)
    assert registered.payload["name"] == "32-ID FlyScan recon"
    assert registered.payload["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert registered.payload["byte_size"] == 1024


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_dataset.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[0].causation_id == causation


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deny_deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await register_dataset.bind(deny_deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
    # Nothing should have been appended.
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events == []


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
async def test_handler_raises_producing_run_not_found_when_run_does_not_exist() -> None:
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW)
    missing_run = uuid4()
    with pytest.raises(ProducingRunNotFoundError) as exc_info:
        await register_dataset.bind(deps)(
            _good_command(producing_run_id=missing_run),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.run_id == missing_run


@pytest.mark.unit
async def test_handler_loads_existing_run_and_appends_with_link() -> None:
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_dataset.bind(deps)(
        _good_command(producing_run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[0].payload["producing_run_id"] == str(run_id)


@pytest.mark.unit
async def test_handler_raises_linked_subject_not_found_when_subject_missing() -> None:
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW)
    missing_subject = uuid4()
    with pytest.raises(LinkedSubjectNotFoundError) as exc_info:
        await register_dataset.bind(deps)(
            _good_command(subject_id=missing_subject),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.subject_id == missing_subject


@pytest.mark.unit
async def test_handler_loads_existing_subject_and_appends_with_link() -> None:
    store = InMemoryEventStore()
    subject_id = uuid4()
    await _seed_subject(store, subject_id)
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_dataset.bind(deps)(
        _good_command(subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[0].payload["subject_id"] == str(subject_id)


@pytest.mark.unit
async def test_handler_raises_derived_from_not_found_collecting_all_missing() -> None:
    store = InMemoryEventStore()
    existing_id = uuid4()
    missing_a = uuid4()
    missing_b = uuid4()
    await _seed_dataset(store, existing_id)
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    with pytest.raises(DerivedFromDatasetsNotFoundError) as exc_info:
        await register_dataset.bind(deps)(
            _good_command(derived_from=frozenset({existing_id, missing_a, missing_b})),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert set(exc_info.value.missing_ids) == {missing_a, missing_b}


@pytest.mark.unit
async def test_handler_accepts_full_cross_agg_context() -> None:
    store = InMemoryEventStore()
    run_id = uuid4()
    subject_id = uuid4()
    derived_id = uuid4()
    await _seed_run(store, run_id)
    await _seed_subject(store, subject_id)
    await _seed_dataset(store, derived_id)
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    await register_dataset.bind(deps)(
        _good_command(
            producing_run_id=run_id,
            subject_id=subject_id,
            derived_from=frozenset({derived_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[0].payload["producing_run_id"] == str(run_id)
    assert events[0].payload["subject_id"] == str(subject_id)
    assert events[0].payload["derived_from"] == [str(derived_id)]


# Defensive AlreadyExists: tested at the decider layer (state non-None).
# The handler's safety net against UUIDv7 collisions is the
# EventStore's ConcurrencyError on expected_version=0, which is
# infra-level (tested in tests/integration/test_postgres_event_store.py).


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_data_includes_register_dataset_and_get_dataset() -> None:
    deps = build_deps(ids=[_DATASET_ID, _REG_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.register_dataset)
    assert callable(handlers.get_dataset)
