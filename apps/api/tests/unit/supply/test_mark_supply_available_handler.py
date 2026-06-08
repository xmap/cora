"""Application-handler tests for `mark_supply_available` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyCannotMarkAvailableError,
    SupplyNotFoundError,
    SupplyRegistered,
    event_type_name,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import mark_supply_available
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 14, 11, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005611")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000005612")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-000000005613")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_unknown_supply(store: InMemoryEventStore) -> None:
    """Seed a registered (Unknown) Supply into the store."""
    genesis = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="2-BM LN2",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_PRIOR,
    )
    new_event = to_new_event(
        event_type=event_type_name(genesis),
        payload=to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=_GENESIS_EVENT_ID,
        command_name="RegisterSupply",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Supply", stream_id=_SUPPLY_ID, expected_version=0, events=[new_event]
    )


def _build_deps(
    *,
    event_store: InMemoryEventStore,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_TRANSITION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_appends_supply_marked_available_event() -> None:
    store = InMemoryEventStore()
    await _seed_unknown_supply(store)
    deps = _build_deps(event_store=store)
    handler = mark_supply_available.bind(deps)

    await handler(
        MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="operator walkdown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Supply", _SUPPLY_ID)
    assert version == 2
    assert len(events) == 2
    transition = events[1]
    assert transition.event_type == "SupplyMarkedAvailable"
    assert transition.payload == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Unknown",
        "reason": "operator walkdown",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_raises_when_supply_not_found() -> None:
    store = InMemoryEventStore()  # empty
    deps = _build_deps(event_store=store)
    handler = mark_supply_available.bind(deps)

    with pytest.raises(SupplyNotFoundError):
        await handler(
            MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_mark_available_when_re_marking() -> None:
    """Strict-not-idempotent: re-marking an already-Available supply raises."""
    store = InMemoryEventStore()
    await _seed_unknown_supply(store)
    deps = _build_deps(event_store=store)
    handler = mark_supply_available.bind(deps)
    await handler(
        MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Now status is Available; second call must raise.
    deps2 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000005614")],
        now=_NOW,
        event_store=store,
    )
    handler2 = mark_supply_available.bind(deps2)
    with pytest.raises(SupplyCannotMarkAvailableError):
        await handler2(
            MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_unknown_supply(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = mark_supply_available.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed_unknown_supply(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = mark_supply_available.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            MarkSupplyAvailable(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Supply", _SUPPLY_ID)
    assert version == 1  # only the genesis from _seed_unknown_supply
    assert events[-1].event_type == "SupplyRegistered"
