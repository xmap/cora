"""Application-handler tests for `degrade_supply` slice.

Built via the `make_supply_update_handler` factory hoisted at the
rule-of-three trigger (triggered by the 4 transition slices). Tests use the
public `bind` seam, so factory implementation is invisible.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyCannotDegradeError,
    SupplyMarkedAvailable,
    SupplyNotFoundError,
    SupplyRegistered,
    event_type_name,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import degrade_supply
from cora.supply.features.degrade_supply import DegradeSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 14, 11, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005711")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000005712")
_MARK_AVAILABLE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005713")
_DEGRADE_EVENT_ID = UUID("01900000-0000-7000-8000-000000005714")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_available_supply(store: InMemoryEventStore) -> None:
    """Seed a registered + marked-Available Supply (status = Available)."""
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


def _build_deps(
    *,
    event_store: InMemoryEventStore,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_DEGRADE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_appends_supply_degraded_event() -> None:
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store)
    handler = degrade_supply.bind(deps)

    await handler(
        DegradeSupply(supply_id=_SUPPLY_ID, reason="half-current"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Supply", _SUPPLY_ID)
    assert version == 3
    transition = events[2]
    assert transition.event_type == "SupplyDegraded"
    assert transition.payload == {
        "supply_id": str(_SUPPLY_ID),
        "from_status": "Available",
        "reason": "half-current",
        "trigger": "Operator",
        "triggered_by": str(_ACTOR_ID),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
async def test_handler_raises_when_supply_not_found() -> None:
    store = InMemoryEventStore()  # empty
    deps = _build_deps(event_store=store)
    handler = degrade_supply.bind(deps)
    with pytest.raises(SupplyNotFoundError):
        await handler(
            DegradeSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_degrade_when_re_degrading() -> None:
    """Strict-not-idempotent: re-degrading raises SupplyCannotDegradeError."""
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store)
    handler = degrade_supply.bind(deps)
    await handler(
        DegradeSupply(supply_id=_SUPPLY_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000005715")],
        now=_NOW,
        event_store=store,
    )
    handler2 = degrade_supply.bind(deps2)
    with pytest.raises(SupplyCannotDegradeError):
        await handler2(
            DegradeSupply(supply_id=_SUPPLY_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_available_supply(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = degrade_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DegradeSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
