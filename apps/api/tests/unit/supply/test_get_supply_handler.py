"""Application-handler tests for `get_supply` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyRegistered,
    SupplyStatus,
    event_type_name,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import get_supply
from cora.supply.features.get_supply import GetSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005711")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000005712")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed(store: InMemoryEventStore) -> None:
    genesis = SupplyRegistered(
        supply_id=_SUPPLY_ID,
        scope="Beamline",
        kind="LiquidNitrogen",
        name="2-BM LN2",
        trigger="Operator",
        triggered_by=_ACTOR_ID,
        occurred_at=_NOW,
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


@pytest.mark.unit
async def test_handler_returns_supply_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_supply.bind(deps)
    state = await handler(
        GetSupply(supply_id=_SUPPLY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert state is not None
    assert state.id == _SUPPLY_ID
    assert state.kind == "LiquidNitrogen"
    assert state.status == SupplyStatus.UNKNOWN


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()  # empty
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_supply.bind(deps)
    state = await handler(
        GetSupply(supply_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert state is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetSupply(supply_id=_SUPPLY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
