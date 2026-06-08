"""Handler tests for the `rate_decision` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.decision.aggregates.decision import (
    DecisionNotFoundError,
    DecisionRating,
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.decision.errors import UnauthorizedError
from cora.decision.features import rate_decision
from cora.decision.features.rate_decision import RateDecision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_DECISION_ID = UUID("01900000-0000-7000-8000-00000000d001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d002")
_RATE_EVENT_ID = UUID("01900000-0000-7000-8000-00000000d003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_RATE_EVENT_ID],
        now=_T1,
        event_store=event_store,
        deny=deny,
    )


async def _seed_decision(store: InMemoryEventStore) -> None:
    genesis = DecisionRegistered(
        decision_id=_DECISION_ID,
        decided_by=ActorId(uuid4()),
        context="RunDebrief",
        choice="NominalCompletion",
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=None,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=None,
        reasoning_signature=None,
        occurred_at=_T0,
    )
    await store.append(
        stream_type="Decision",
        stream_id=_DECISION_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_GENESIS_EVENT_ID,
                command_name="RegisterDecision",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_appends_decision_rated_event() -> None:
    store = InMemoryEventStore()
    await _seed_decision(store)
    deps = _build_deps(event_store=store)
    handler = rate_decision.bind(deps)
    await handler(
        RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.USEFUL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Decision", _DECISION_ID)
    assert version == 2
    assert events[-1].event_type == "DecisionRated"
    assert events[-1].payload["rating"] == "useful"
    assert events[-1].payload["rated_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_handler_carries_comment() -> None:
    store = InMemoryEventStore()
    await _seed_decision(store)
    deps = _build_deps(event_store=store)
    handler = rate_decision.bind(deps)
    await handler(
        RateDecision(
            decision_id=_DECISION_ID,
            rating=DecisionRating.MISLEADING,
            comment="missed the temperature excursion",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Decision", _DECISION_ID)
    assert events[-1].payload["comment"] == "missed the temperature excursion"


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    await _seed_decision(store)
    deps = _build_deps(event_store=store)
    handler = rate_decision.bind(deps)
    result = await handler(
        RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.IGNORED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_not_found_for_unknown_decision() -> None:
    deps = _build_deps()
    handler = rate_decision.bind(deps)
    with pytest.raises(DecisionNotFoundError):
        await handler(
            RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.USEFUL),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = rate_decision.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.USEFUL),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_to_stream() -> None:
    """Authorize-denial MUST NOT mutate the Decision stream.

    Mirrors the deny-no-write pattern from the Agent BC cleanup.
    """
    store = InMemoryEventStore()
    await _seed_decision(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = rate_decision.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.USEFUL),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Decision", _DECISION_ID)
    assert version == 1  # only the seeded genesis
    assert len(events) == 1
    assert events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_handler_multiple_ratings_all_persist() -> None:
    """Multiple ratings from the same actor all append to the stream
    (audit trail). The projection takes latest-wins, but the stream
    keeps every event."""
    store = InMemoryEventStore()
    await _seed_decision(store)
    # Different id for second event so to_new_event doesn't collide.
    second_event_id = UUID("01900000-0000-7000-8000-00000000d004")
    deps1 = _build_deps_shared(ids=[_RATE_EVENT_ID], now=_T1, event_store=store)
    await rate_decision.bind(deps1)(
        RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.USEFUL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(ids=[second_event_id], now=_T1, event_store=store)
    await rate_decision.bind(deps2)(
        RateDecision(decision_id=_DECISION_ID, rating=DecisionRating.MISLEADING),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Decision", _DECISION_ID)
    assert version == 3
    rated_events = [e for e in events if e.event_type == "DecisionRated"]
    assert len(rated_events) == 2
    assert [e.payload["rating"] for e in rated_events] == ["useful", "misleading"]
