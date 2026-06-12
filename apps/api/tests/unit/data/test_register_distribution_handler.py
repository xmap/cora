"""Unit tests for the `register_distribution` application handler.

Mirror of `register_dataset` handler test shape: VOs validated, authz
called, idempotency-not-tested (wire decorator's job), cross-aggregate
context loaded from real in-memory event store + SupplyLookup stub.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetNotFoundError,
)
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.distribution import (
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumMismatchError,
    DistributionSupplyNotFoundError,
)
from cora.data.features import register_distribution
from cora.data.features.register_distribution import RegisterDistribution
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.supply_lookup import (
    SingleSupplyLookup,
    SupplyLookupResult,
    UnknownSupplyLookup,
)
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_OTHER_SHA256 = "b" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000d1571")
_REG_EVENT_ID = UUID("01900000-0000-7000-8000-0000000d1572")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DATASET_ID = UUID("01900000-0000-7000-8000-00000000da7a")
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005519")


def _good_command(**overrides: object) -> RegisterDistribution:
    base: dict[str, object] = {
        "dataset_id": _DATASET_ID,
        "supply_id": _SUPPLY_ID,
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "conforms_to": frozenset[str](),
        "access_protocol": "S3",
    }
    base.update(overrides)
    return RegisterDistribution(**base)  # type: ignore[arg-type]


def _storage_supply_ref(
    *,
    supply_id: UUID = _SUPPLY_ID,
    kind: str = "Storage",
    status: str = "Available",
) -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=supply_id,
        kind=kind,
        name="primary-storage",
        status=status,
        facility_code="aps",
    )


async def _seed_dataset(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    checksum_value: str = _GOOD_SHA256,
    byte_size: int = 1024,
) -> None:
    event = DatasetRegistered(
        dataset_id=dataset_id,
        name="seed",
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=checksum_value,
        byte_size=byte_size,
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
async def test_handler_returns_new_distribution_id_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    distribution_id = await register_distribution.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert distribution_id == _DISTRIBUTION_ID


@pytest.mark.unit
async def test_handler_appends_distribution_registered_event_with_canonical_payload() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    await register_distribution.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Distribution", _DISTRIBUTION_ID)
    assert version == 1
    assert [e.event_type for e in events] == ["DistributionRegistered"]
    registered = events[0]
    assert registered.event_id == _REG_EVENT_ID
    assert registered.metadata == {"command": "RegisterDistribution"}
    payload = registered.payload
    assert payload["distribution_id"] == str(_DISTRIBUTION_ID)
    assert payload["dataset_id"] == str(_DATASET_ID)
    assert payload["supply_id"] == str(_SUPPLY_ID)
    assert payload["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert payload["checksum"] == {"algorithm": "sha256", "value": _GOOD_SHA256}
    assert payload["byte_size"] == 1024
    assert payload["access_protocol"] == "S3"
    assert payload["registered_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    await register_distribution.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Distribution", _DISTRIBUTION_ID)
    assert events[0].causation_id == causation


# ---------- Authz ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(
        ids=[_DISTRIBUTION_ID, _REG_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    with pytest.raises(UnauthorizedError) as exc:
        await register_distribution.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.reason == "denied for test"
    # Nothing should have been appended.
    events, _ = await store.load("Distribution", _DISTRIBUTION_ID)
    assert events == []


# ---------- Cross-aggregate validation ----------


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_when_dataset_missing() -> None:
    store = InMemoryEventStore()
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    missing_dataset_id = uuid4()
    with pytest.raises(DatasetNotFoundError):
        await register_distribution.bind(deps)(
            _good_command(dataset_id=missing_dataset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_supply_not_found_when_supply_lookup_returns_none() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=UnknownSupplyLookup())
    with pytest.raises(DistributionSupplyNotFoundError) as exc:
        await register_distribution.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.supply_id == _SUPPLY_ID


@pytest.mark.unit
async def test_handler_raises_on_non_storage_supply_kind() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(
        base,
        supply_lookup=SingleSupplyLookup(_storage_supply_ref(kind="Consumable")),
    )
    with pytest.raises(DistributionCannotRegisterOnNonStorageSupplyError):
        await register_distribution.bind(deps)(
            _good_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_on_checksum_mismatch_against_dataset() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID, checksum_value=_GOOD_SHA256)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(base, supply_lookup=SingleSupplyLookup(_storage_supply_ref()))
    with pytest.raises(DistributionChecksumMismatchError):
        await register_distribution.bind(deps)(
            _good_command(checksum_value=_OTHER_SHA256),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_binds_against_decommissioned_supply() -> None:
    """Per L28: status-agnostic bind on Supply (only kind is gated)."""
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    base = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW, event_store=store)
    deps = replace(
        base,
        supply_lookup=SingleSupplyLookup(_storage_supply_ref(status="Decommissioned")),
    )
    distribution_id = await register_distribution.bind(deps)(
        _good_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert distribution_id == _DISTRIBUTION_ID


# ---------- Wire bundle ----------


@pytest.mark.unit
def test_wire_data_includes_register_distribution() -> None:
    deps = build_deps(ids=[_DISTRIBUTION_ID, _REG_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.register_distribution)
