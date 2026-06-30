"""Unit tests for the `discard_distribution` application handler.

Update-style handler: loads the Distribution stream, the parent Dataset,
and the projection-backed sibling set, runs the guarded decider, and
appends DistributionDiscarded with optimistic concurrency. The sibling
set is injected via a SeededDatasetDistributionLookup over the Kernel.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.aggregates.dataset.events import (
    DatasetRegistered,
)
from cora.data.aggregates.dataset.events import (
    event_type_name as dataset_event_type_name,
)
from cora.data.aggregates.dataset.events import (
    to_payload as dataset_to_payload,
)
from cora.data.aggregates.distribution import (
    DistributionCannotDiscardError,
    DistributionCannotDiscardLastVerifiedError,
    DistributionNotFoundError,
    DistributionRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import discard_distribution
from cora.data.features.discard_distribution import DiscardDistribution
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
    SeededDatasetDistributionLookup,
)
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-0000000000d1")
_DISTRIBUTION_ID = UUID("01900000-0000-7000-8000-0000000000f1")
_SIBLING_ID = UUID("01900000-0000-7000-8000-0000000000f2")
_SUPPLY_A = UUID("01900000-0000-7000-8000-0000000000a1")
_SUPPLY_B = UUID("01900000-0000-7000-8000-0000000000b1")
_DISCARD_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ee01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-0000000000bb"))


async def _seed_dataset(store: InMemoryEventStore, dataset_id: UUID) -> None:
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
    await store.append(
        stream_type="Dataset",
        stream_id=dataset_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=dataset_event_type_name(event),
                payload=dataset_to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDataset",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


async def _seed_distribution(
    store: InMemoryEventStore, *, distribution_id: UUID, supply_id: UUID
) -> None:
    event = DistributionRegistered(
        distribution_id=distribution_id,
        dataset_id=_DATASET_ID,
        supply_id=supply_id,
        uri="s3://b/k",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=0,
        media_type="application/x-hdf5",
        conforms_to=frozenset(),
        access_protocol="S3",
        occurred_at=_NOW,
        registered_by=_SEED_ACTOR_ID,
    )
    await store.append(
        stream_type="Distribution",
        stream_id=distribution_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RegisterDistribution",
                correlation_id=_CORRELATION_ID,
                principal_id=uuid4(),
            )
        ],
    )


def _with_siblings(deps: Kernel, siblings: tuple[DatasetDistributionLookupResult, ...]) -> Kernel:
    return replace(
        deps,
        dataset_distribution_lookup=SeededDatasetDistributionLookup({_DATASET_ID: siblings}),
    )


def _verified_sibling_on_b() -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=_SIBLING_ID,
        dataset_id=_DATASET_ID,
        supply_id=_SUPPLY_B,
        status="Verified",
    )


def _target_row() -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=_DISTRIBUTION_ID,
        dataset_id=_DATASET_ID,
        supply_id=_SUPPLY_A,
        status="Registered",
    )


@pytest.mark.unit
async def test_handler_appends_discarded_with_trimmed_reason() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps = _with_siblings(deps, (_target_row(), _verified_sibling_on_b()))
    await discard_distribution.bind(deps)(
        DiscardDistribution(
            distribution_id=_DISTRIBUTION_ID,
            reason="  bytes reclaimed from cold tier  ",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Distribution", _DISTRIBUTION_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "DistributionRegistered",
        "DistributionDiscarded",
    ]
    discarded = events[1]
    assert discarded.event_id == _DISCARD_EVENT_ID
    assert discarded.metadata == {"command": "DiscardDistribution"}
    assert discarded.payload == {
        "distribution_id": str(_DISTRIBUTION_ID),
        "reason": "bytes reclaimed from cold tier",
        "occurred_at": _NOW.isoformat(),
        "discarded_by": str(_PRINCIPAL_ID),
    }


@pytest.mark.unit
async def test_handler_raises_not_found_when_distribution_missing() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps = _with_siblings(deps, (_verified_sibling_on_b(),))
    with pytest.raises(DistributionNotFoundError):
        await discard_distribution.bind(deps)(
            DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_last_verified_without_redundant_sibling() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps = _with_siblings(deps, (_target_row(),))
    with pytest.raises(DistributionCannotDiscardLastVerifiedError):
        await discard_distribution.bind(deps)(
            DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="reclaim"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_discard_when_already_discarded() -> None:
    """Strict-not-idempotent: re-discarding raises on the second call."""
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps = _with_siblings(deps, (_target_row(), _verified_sibling_on_b()))
    await discard_distribution.bind(deps)(
        DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps2 = _with_siblings(deps2, (_target_row(), _verified_sibling_on_b()))
    with pytest.raises(DistributionCannotDiscardError):
        await discard_distribution.bind(deps2)(
            DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deny_deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store, deny=True)
    deny_deps = _with_siblings(deny_deps, (_target_row(), _verified_sibling_on_b()))
    with pytest.raises(UnauthorizedError) as exc_info:
        await discard_distribution.bind(deny_deps)(
            DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="X"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    store = InMemoryEventStore()
    await _seed_dataset(store, _DATASET_ID)
    await _seed_distribution(store, distribution_id=_DISTRIBUTION_ID, supply_id=_SUPPLY_A)
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW, event_store=store)
    deps = _with_siblings(deps, (_target_row(), _verified_sibling_on_b()))
    await discard_distribution.bind(deps)(
        DiscardDistribution(distribution_id=_DISTRIBUTION_ID, reason="X"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Distribution", _DISTRIBUTION_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_data_includes_discard_distribution() -> None:
    deps = build_deps(ids=[_DISCARD_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.discard_distribution)
