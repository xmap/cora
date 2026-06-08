"""Application-handler tests for `register_supply` slice.

In-memory event store + AllowAllAuthorize (or DenyAllAuthorize). The
idempotency-wrap is applied at wire.py and is not exercised here;
we test the bare handler returned by `register_supply.bind(deps)`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import SupplyScope
from cora.supply.errors import UnauthorizedError
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000005511")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000005512")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_returns_generated_supply_id() -> None:
    deps = _build_deps()
    handler = register_supply.bind(deps)
    result = await handler(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_supply_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM LN2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "SupplyRegistered"
    assert stored.payload == {
        "supply_id": str(_NEW_ID),
        "scope": "Beamline",
        "kind": "LiquidNitrogen",
        "name": "2-BM LN2",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterSupply"}


@pytest.mark.unit
async def test_handler_trims_kind_and_name() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_supply.bind(deps)
    await handler(
        RegisterSupply(
            scope=SupplyScope.FACILITY,
            kind="  PhotonBeam  ",
            name="  APS storage-ring beam  ",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Supply", _NEW_ID)
    assert events[0].payload["kind"] == "PhotonBeam"
    assert events[0].payload["name"] == "APS storage-ring beam"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_supply.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterSupply(scope=SupplyScope.BEAMLINE, kind="LiquidNitrogen", name="2-BM"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Supply", _NEW_ID)
    assert version == 0
    assert events == []
