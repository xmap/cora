"""Tests for the Supply status monitor runtime (`cora/supply/_monitor.py`).

`record_observation` is pinned deterministically against a real event
store: it maps an observation to the matching transition, is silent on a
re-asserted status (the status-change-only contract the loop depends on
for latched substrates), refuses a status a monitor may not drive, and
no-ops on an unmapped code or an unparseable status. The retry loop and
lifespan are covered for the empty-map no-op path and for a fake-observer
drive that records one observation end to end.

Shaped after `test_enclosure_permit_monitor.py`, the sibling runtime.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StoredEvent
from cora.supply._monitor import (
    SUPPLY_STATUS_MONITOR_SOURCE_ID,
    record_observation,
    run_supply_status_monitor,
    supply_status_monitor_lifespan,
)
from cora.supply.aggregates.supply import SupplyStatus
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.mark_supply_available import bind as bind_mark_available
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register_supply
from cora.supply.ports.supply_observer import (
    AlwaysQuietSupplyObserver,
    SupplyObservation,
    SupplyObserver,
    SupplyObserverScope,
)
from tests.integration._helpers import build_postgres_deps

_T = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = uuid4()
_CORRELATION_ID = uuid4()
_FLOW2_PV = "2bmBLEPS:BLEPS:FLOW2_TRIP"


def _deps(db_pool: asyncpg.Pool) -> Kernel:
    return build_postgres_deps(db_pool, now=_T, ids=[uuid4() for _ in range(24)])


def _obs(
    code: str,
    status: str,
    *,
    reason: str = "Flow2 below set point",
    pv: str = _FLOW2_PV,
) -> SupplyObservation:
    return SupplyObservation(
        supply_code=code,
        observed_status=status,
        observed_at=_T,
        reason=reason,
        source_kind="EpicsPv",
        source_id=pv,
    )


async def _available_supply(deps: Kernel, code: str) -> UUID:
    """Register a CoolingWater supply and walk it to Available."""
    supply_id = await bind_register_supply(deps)(
        RegisterSupply(kind="CoolingWater", name=code, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_mark_available(deps)(
        MarkSupplyAvailable(
            supply_id=supply_id,
            reason="Operator walkdown at beamtime start; all eight circuits flowing.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=uuid4(),
    )
    return supply_id


async def _transitions(deps: Kernel, supply_id: UUID, event_type: str) -> list[StoredEvent]:
    events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
    return [e for e in events if e.event_type == event_type]


@pytest.mark.integration
async def test_record_observation_writes_the_transition(db_pool: asyncpg.Pool) -> None:
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    await record_observation(deps, _obs(code, "Unavailable"), {code: supply_id})

    events = await _transitions(deps, supply_id, "SupplyMarkedUnavailable")
    assert len(events) == 1
    payload = events[0].payload
    assert payload["trigger"] == "Monitor"
    assert payload["triggered_by"] == str(SUPPLY_STATUS_MONITOR_SOURCE_ID)
    assert payload["monitor_ref"] == f"EpicsPv:{_FLOW2_PV}"
    assert payload["from_status"] == SupplyStatus.AVAILABLE.value


@pytest.mark.integration
async def test_record_observation_carries_the_channel_in_the_reason(
    db_pool: asyncpg.Pool,
) -> None:
    """The status says a run cannot draw on it; the reason says which circuit.

    This is what makes one Supply per resource sufficient instead of one
    per cooling circuit: the failing channel is never lost, it just does
    not get its own aggregate.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    await record_observation(
        deps,
        _obs(code, "Unavailable", reason="Flow2 below set point (M1 and DMM circuit)"),
        {code: supply_id},
    )

    events = await _transitions(deps, supply_id, "SupplyMarkedUnavailable")
    assert events[0].payload["reason"] == "Flow2 below set point (M1 and DMM circuit)"


@pytest.mark.integration
async def test_record_observation_is_silent_on_a_re_asserted_status(
    db_pool: asyncpg.Pool,
) -> None:
    """A latched signal republishing a still-true fault writes one event, not two.

    The behaviour the whole runtime leans on: BLEPS latches, so every
    reconnect replays every standing fault. Under the strict
    operator-side contract this would raise once per channel per
    reconnect.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    code_to_id = {code: supply_id}

    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)
    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)
    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)

    assert len(await _transitions(deps, supply_id, "SupplyMarkedUnavailable")) == 1


@pytest.mark.integration
async def test_record_observation_refuses_to_restore_a_supply(db_pool: asyncpg.Pool) -> None:
    """A monitor may not drive Available; coming back is an operator's word.

    The adapter should send `Recovering` instead. Available raises rather
    than no-opping even when it matches the current status, so the
    adapter bug surfaces instead of hiding.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    with pytest.raises(Exception, match="Monitor trigger cannot drive"):
        await record_observation(deps, _obs(code, "Available"), {code: supply_id})

    assert await _transitions(deps, supply_id, "SupplyMarkedAvailable") != []
    assert await _transitions(deps, supply_id, "SupplyRestored") == []


@pytest.mark.integration
async def test_record_observation_walks_down_then_to_recovering(db_pool: asyncpg.Pool) -> None:
    """Unavailable then Recovering is the full monitor-drivable arc.

    Recovering is as far as a monitor gets: the signal reading clear is
    an observation, the resource being back is a person's judgment.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    code_to_id = {code: supply_id}

    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)
    await record_observation(
        deps, _obs(code, "Recovering", reason="Flow2 back above set point"), code_to_id
    )

    assert len(await _transitions(deps, supply_id, "SupplyMarkedRecovering")) == 1


@pytest.mark.integration
async def test_record_observation_ignores_an_unmapped_code(db_pool: asyncpg.Pool) -> None:
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    await record_observation(deps, _obs("not-a-supply", "Unavailable"), {code: supply_id})

    assert await _transitions(deps, supply_id, "SupplyMarkedUnavailable") == []


@pytest.mark.integration
async def test_record_observation_ignores_an_unparseable_status(db_pool: asyncpg.Pool) -> None:
    """An adapter must flatten to the codomain; junk is dropped, not guessed."""
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    await record_observation(deps, _obs(code, "VeryBroken"), {code: supply_id})

    events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
    assert [e.event_type for e in events] == ["SupplyRegistered", "SupplyMarkedAvailable"]


@pytest.mark.integration
async def test_run_monitor_returns_immediately_when_nothing_is_mapped(
    db_pool: asyncpg.Pool,
) -> None:
    """No configured supplies means no subscription, not an idle reconnect loop."""
    deps = _deps(db_pool)
    await asyncio.wait_for(
        run_supply_status_monitor(observer=AlwaysQuietSupplyObserver(), kernel=deps, code_to_id={}),
        timeout=5,
    )


@pytest.mark.integration
async def test_stub_observer_yields_nothing(db_pool: asyncpg.Pool) -> None:
    """The always-pass stub is an empty stream, since Available is un-drivable.

    A stub that yielded `Available` observations would raise on every
    tick, so silence is the faithful representation of a beamline with
    nothing wrong.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    scope = SupplyObserverScope(supply_codes=frozenset({code}))

    observed = [obs async for obs in AlwaysQuietSupplyObserver().observe(scope)]

    assert observed == []
    events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
    assert len(events) == 2


@pytest.mark.integration
async def test_lifespan_drives_an_observation_and_cancels_cleanly(
    db_pool: asyncpg.Pool,
) -> None:
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    recorded = asyncio.Event()

    class _OneShotObserver:
        def observe(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
            return self._drain(scope)

        async def _drain(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
            for supply_code in sorted(scope.supply_codes):
                yield _obs(supply_code, "Unavailable")
            recorded.set()
            await asyncio.sleep(3600)

    observer: SupplyObserver = _OneShotObserver()
    async with supply_status_monitor_lifespan(
        observer=observer, kernel=deps, code_to_id={code: supply_id}
    ):
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(recorded.wait(), timeout=5)
        await asyncio.sleep(0.05)

    assert len(await _transitions(deps, supply_id, "SupplyMarkedUnavailable")) == 1


@pytest.mark.integration
async def test_clear_on_a_healthy_supply_records_nothing(db_pool: asyncpg.Pool) -> None:
    """Observers report levels; "clear" only means something for a downed supply.

    This is the gate that replaced the adapter's edge memory. On a healthy
    beamline every initial reading is clear, so without it the decider
    would reject each one.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)

    await record_observation(
        deps, _obs(code, "Recovering", reason="BLEPS trips clear"), {code: supply_id}
    )

    events, _ = await deps.event_store.load(stream_type="Supply", stream_id=supply_id)
    assert [e.event_type for e in events] == ["SupplyRegistered", "SupplyMarkedAvailable"]


@pytest.mark.integration
async def test_clear_on_a_downed_supply_records_recovering(db_pool: asyncpg.Pool) -> None:
    """The same observation IS news once the supply is actually Unavailable."""
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    code_to_id = {code: supply_id}

    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)
    await record_observation(deps, _obs(code, "Recovering", reason="BLEPS trips clear"), code_to_id)

    assert len(await _transitions(deps, supply_id, "SupplyMarkedRecovering")) == 1


@pytest.mark.integration
async def test_a_re_asserted_clear_level_stays_silent(db_pool: asyncpg.Pool) -> None:
    """Levels repeat; the record must not.

    Once Recovering is recorded the supply is no longer Unavailable, so
    every later clear reading is dropped by the gate rather than rejected
    by the decider.
    """
    code = f"cooling-water-{uuid4().hex[:8]}"
    deps = _deps(db_pool)
    supply_id = await _available_supply(deps, code)
    code_to_id = {code: supply_id}

    await record_observation(deps, _obs(code, "Unavailable"), code_to_id)
    for _ in range(4):
        await record_observation(deps, _obs(code, "Recovering"), code_to_id)

    assert len(await _transitions(deps, supply_id, "SupplyMarkedRecovering")) == 1
