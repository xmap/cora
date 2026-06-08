"""Application-handler tests for `deregister_supply` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyCannotDeregisterError,
    SupplyMarkedAvailable,
    SupplyNotFoundError,
    SupplyRegistered,
    event_type_name,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import deregister_supply
from cora.supply.features.deregister_supply import DeregisterSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 27, 11, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005911")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000005912")
_MARK_AVAILABLE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005913")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-000000005914")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_available_supply(store: InMemoryEventStore) -> None:
    genesis = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="2-BM LN2",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_PRIOR,
    )
    mark = SupplyMarkedAvailable(
        supply_id=_SUPPLY_ID,
        from_status="Unknown",
        reason="walkdown",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_PRIOR,
    )
    for ev, eid, cmd in [
        (genesis, _GENESIS_EVENT_ID, "RegisterSupply"),
        (mark, _MARK_AVAILABLE_EVENT_ID, "MarkSupplyAvailable"),
    ]:
        new_event = to_new_event(
            event_type=event_type_name(ev),
            payload=to_payload(ev),
            occurred_at=ev.occurred_at,
            event_id=eid,
            command_name=cmd,
            correlation_id=_CORRELATION_ID,
            causation_id=None,
            principal_id=_PRINCIPAL_ID,
        )
        version_before = (await store.load("Supply", _SUPPLY_ID))[1]
        await store.append(
            stream_type="Supply",
            stream_id=_SUPPLY_ID,
            expected_version=version_before,
            events=[new_event],
        )


def _build_deps(*, event_store: InMemoryEventStore, deny: bool = False) -> Kernel:
    return _build_deps_shared(
        ids=[_TRANSITION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_appends_supply_deregistered_event() -> None:
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store)
    handler = deregister_supply.bind(deps)

    await handler(
        DeregisterSupply(supply_id=_SUPPLY_ID, reason="duplicate; re-registering"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Supply", _SUPPLY_ID)
    assert version == 3
    transition = events[2]
    assert transition.event_type == "SupplyDeregistered"
    assert transition.payload["from_status"] == "Available"
    assert transition.payload["reason"] == "duplicate; re-registering"
    assert transition.payload["trigger"] == "Operator"


@pytest.mark.unit
async def test_handler_raises_when_supply_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = deregister_supply.bind(deps)
    with pytest.raises(SupplyNotFoundError):
        await handler(
            DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deregister_when_already_decommissioned() -> None:
    """Strict-not-idempotent: second deregister on the same stream raises."""
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store)
    handler = deregister_supply.bind(deps)
    await handler(
        DeregisterSupply(supply_id=_SUPPLY_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000005915")],
        now=_NOW,
        event_store=store,
    )
    handler2 = deregister_supply.bind(deps2)
    with pytest.raises(SupplyCannotDeregisterError):
        await handler2(
            DeregisterSupply(supply_id=_SUPPLY_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = deregister_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DeregisterSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
