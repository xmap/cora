"""Unit tests for the `promote_dataset` application handler.

Update-style handler: load + fold + decide + append. Loads peer
Datasets in `state.derived_from` for the lineage-must-be-Production
guard. NOT idempotency-wrapped (strict-not-idempotent at decider).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.data import DataHandlers, UnauthorizedError, wire_data
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetAlreadyPromotedError,
    DatasetCannotPromoteError,
)
from cora.data.aggregates.dataset.events import (
    DatasetPromoted,
    DatasetRegistered,
    event_type_name,
    to_payload,
)
from cora.data.features import promote_dataset
from cora.data.features.promote_dataset import PromoteDataset
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from tests.unit._helpers import build_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_DATASET_ID = UUID("01900000-0000-7000-8000-000000007e01")
_PROMOTE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007e02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SEED_ACTOR_ID = UUID("01900000-0000-7000-8000-0000000000bb")


async def _seed_registered(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    producing_run_id: UUID | None = None,
    producing_run_end_state: str | None = None,
    derived_from: frozenset[UUID] = frozenset(),
    intent: str = "Trial",
) -> None:
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
        producing_run_id=producing_run_id,
        subject_id=None,
        derived_from=derived_from,
        occurred_at=_NOW,
        registered_by=ActorId(_SEED_ACTOR_ID),
        producing_run_end_state=producing_run_end_state,
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


async def _seed_promoted(
    store: InMemoryEventStore,
    dataset_id: UUID,
    *,
    producing_run_id: UUID | None = None,
    producing_run_end_state: str | None = None,
) -> None:
    """Seed a Dataset already in Production intent (registered + promoted)."""
    await _seed_registered(
        store,
        dataset_id,
        producing_run_id=producing_run_id,
        producing_run_end_state=producing_run_end_state,
    )
    from cora.shared.identity import ActorId

    promoted = DatasetPromoted(
        dataset_id=dataset_id,
        reason="initial promotion for tests",
        occurred_at=_NOW,
        promoted_by=ActorId(_SEED_ACTOR_ID),
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


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)
    result = await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=_DATASET_ID, reason="passed peer review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_dataset_promoted_with_correct_payload() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=_DATASET_ID, reason="  passed review  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Dataset", _DATASET_ID)
    assert version == 2
    assert [e.event_type for e in events] == ["DatasetRegistered", "DatasetPromoted"]
    promoted = events[1]
    assert promoted.event_id == _PROMOTE_EVENT_ID
    assert promoted.metadata == {"command": "PromoteDataset"}
    assert promoted.payload["dataset_id"] == str(_DATASET_ID)
    # Reason trimmed via PromotionReason VO.
    assert promoted.payload["reason"] == "passed review"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deny_deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store, deny=True)
    with pytest.raises(UnauthorizedError):
        await promote_dataset.bind(deny_deps)(
            PromoteDataset(dataset_id=_DATASET_ID, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Stream untouched: only the seed event.
    _, version = await store.load("Dataset", _DATASET_ID)
    assert version == 1


@pytest.mark.unit
async def test_handler_propagates_causation_id() -> None:
    causation = UUID("01900000-0000-7000-8000-000000007ebb")
    store = InMemoryEventStore()
    await _seed_registered(store, _DATASET_ID)
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=_DATASET_ID, reason="passed review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[1].causation_id == causation


@pytest.mark.unit
async def test_handler_loads_derived_from_and_rejects_when_lineage_trial() -> None:
    """Lineage-must-be-Production guard: handler loads each derived_from
    Dataset; decider rejects if any are still Trial."""
    upstream_id = UUID("01900000-0000-7000-8000-000000007e10")
    store = InMemoryEventStore()
    # Seed upstream as Trial (default).
    await _seed_registered(store, upstream_id)
    # Seed downstream with derived_from referencing the upstream.
    await _seed_registered(
        store,
        _DATASET_ID,
        derived_from=frozenset({upstream_id}),
    )
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(DatasetCannotPromoteError) as exc_info:
        await promote_dataset.bind(deps)(
            PromoteDataset(dataset_id=_DATASET_ID, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "Trial" in exc_info.value.reason
    # Downstream stream untouched.
    _, version = await store.load("Dataset", _DATASET_ID)
    assert version == 1


@pytest.mark.unit
async def test_handler_succeeds_when_lineage_is_production() -> None:
    """Happy path with non-empty lineage: all upstream Datasets in
    Production intent, downstream Dataset successfully promotes."""
    upstream_id = UUID("01900000-0000-7000-8000-000000007e11")
    store = InMemoryEventStore()
    # Seed upstream and immediately promote it.
    await _seed_promoted(store, upstream_id)
    # Seed downstream with derived_from referencing the upstream.
    await _seed_registered(
        store,
        _DATASET_ID,
        derived_from=frozenset({upstream_id}),
    )
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)

    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=_DATASET_ID, reason="lineage validated"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Dataset", _DATASET_ID)
    assert events[-1].event_type == "DatasetPromoted"


@pytest.mark.unit
async def test_handler_raises_already_promoted_on_second_promote() -> None:
    """Strict-not-idempotent: second promote attempt rejects."""
    store = InMemoryEventStore()
    await _seed_promoted(store, _DATASET_ID)
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)

    with pytest.raises(DatasetAlreadyPromotedError):
        await promote_dataset.bind(deps)(
            PromoteDataset(dataset_id=_DATASET_ID, reason="trying again"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_dataset_not_found_for_unknown_dataset() -> None:
    """Handler-level coverage of the empty-stream path: when no
    DatasetRegistered event exists for the target id, fold returns
    None, and the decider raises DatasetNotFoundError. Pinned at
    the handler boundary because this is the route → 404 path."""
    from cora.data.aggregates.dataset import DatasetNotFoundError

    store = InMemoryEventStore()
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW, event_store=store)
    unknown_id = UUID("01900000-0000-7000-8000-000000007e99")
    with pytest.raises(DatasetNotFoundError):
        await promote_dataset.bind(deps)(
            PromoteDataset(dataset_id=unknown_id, reason="trying"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
def test_wire_data_includes_promote_dataset() -> None:
    deps = build_deps(ids=[_PROMOTE_EVENT_ID], now=_NOW)
    handlers = wire_data(deps)
    assert isinstance(handlers, DataHandlers)
    assert callable(handlers.promote_dataset)
