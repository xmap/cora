"""Application-handler tests for `restore_supply` slice (10a-b).

Single-source guard: requires Supply to be in Recovering. Seed
helper takes the supply through register -> mark_available ->
mark_unavailable -> mark_recovering so it lands in Recovering
before the test's restore call.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    SupplyCannotRestoreError,
    SupplyMarkedAvailable,
    SupplyMarkedRecovering,
    SupplyMarkedUnavailable,
    SupplyNotFoundError,
    SupplyRegistered,
    event_type_name,
    to_payload,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features import restore_supply
from cora.supply.features.restore_supply import RestoreSupply
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRIOR = datetime(2026, 5, 14, 11, 0, 0, tzinfo=UTC)
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000005a11")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_ACTOR_ID = ActorId(_PRINCIPAL_ID)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_TRANSITION_EVENT_ID = UUID("01900000-0000-7000-8000-000000005a15")


async def _seed_recovering_supply(store: InMemoryEventStore) -> None:
    """Seed a Supply in Recovering status."""
    events_to_seed = [
        (
            SupplyRegistered(
                supply_id=_SUPPLY_ID,
                scope="Beamline",
                kind="LiquidNitrogen",
                name="2-BM LN2",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_PRIOR,
            ),
            "RegisterSupply",
        ),
        (
            SupplyMarkedAvailable(
                supply_id=_SUPPLY_ID,
                from_status="Unknown",
                reason="walkdown",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_PRIOR,
            ),
            "MarkSupplyAvailable",
        ),
        (
            SupplyMarkedUnavailable(
                supply_id=_SUPPLY_ID,
                from_status="Available",
                reason="beam dump",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_PRIOR,
            ),
            "MarkSupplyUnavailable",
        ),
        (
            SupplyMarkedRecovering(
                supply_id=_SUPPLY_ID,
                from_status="Unavailable",
                reason="beam returning",
                trigger="Operator",
                triggered_by=_ACTOR_ID,
                occurred_at=_PRIOR,
            ),
            "MarkSupplyRecovering",
        ),
    ]
    for ev, cmd in events_to_seed:
        new_event = to_new_event(
            event_type=event_type_name(ev),
            payload=to_payload(ev),
            occurred_at=ev.occurred_at,
            event_id=UUID(int=int(_SUPPLY_ID) + len(cmd)),
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
async def test_handler_appends_supply_restored_event() -> None:
    store = InMemoryEventStore()
    await _seed_recovering_supply(store)
    deps = _build_deps(event_store=store)
    handler = restore_supply.bind(deps)

    await handler(
        RestoreSupply(supply_id=_SUPPLY_ID, reason="ops confirms stable"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Supply", _SUPPLY_ID)
    assert version == 5
    transition = events[4]
    assert transition.event_type == "SupplyRestored"
    assert transition.payload["from_status"] == "Recovering"
    assert transition.payload["reason"] == "ops confirms stable"


@pytest.mark.unit
async def test_handler_raises_when_supply_not_found() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = restore_supply.bind(deps)
    with pytest.raises(SupplyNotFoundError):
        await handler(
            RestoreSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_restore_when_re_restoring() -> None:
    """Strict-not-idempotent: re-restoring an Available (post-restore) raises."""
    store = InMemoryEventStore()
    await _seed_recovering_supply(store)
    deps = _build_deps(event_store=store)
    handler = restore_supply.bind(deps)
    await handler(
        RestoreSupply(supply_id=_SUPPLY_ID, reason="first"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000005a16")],
        now=_NOW,
        event_store=store,
    )
    handler2 = restore_supply.bind(deps2)
    with pytest.raises(SupplyCannotRestoreError):
        await handler2(
            RestoreSupply(supply_id=_SUPPLY_ID, reason="second"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_recovering_supply(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = restore_supply.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RestoreSupply(supply_id=_SUPPLY_ID, reason="r"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
