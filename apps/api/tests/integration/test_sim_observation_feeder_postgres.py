"""Integration: SimObservationFeeder drives the closed-loop loop end to end.

Proves the sim feeder writes through the REAL AppendObservations path (rows
carry is_simulated=True under the distinct sim principal) and pings the
feeder heartbeat, then the gate-review-required dead-feeder transition: a
fresh heartbeat lets a zero-arrival channel stall-flag, a stale heartbeat
(feeder stopped + clock advanced past the ceiling) defers (feed_dead).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._run_supervisor import decide_signal_stall
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import FakeClock, UUIDv7Generator
from cora.run.adapters import (
    SIM_OBSERVATION_FEEDER_AGENT_ID,
    PostgresRunChannelLookup,
    SimObservationFeeder,
    TracePoint,
)
from cora.run.aggregates.run import PostgresFeedHeartbeatStore, PostgresObservationStore
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features.append_observations import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FEED_CEILING_SECONDS = 120.0


async def _seed_run_started(event_store: object, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id, name="sim-feeder Run", plan_id=uuid4(), subject_id=uuid4(), occurred_at=_NOW
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await event_store.append(  # type: ignore[attr-defined]
        stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event]
    )


@pytest.mark.integration
async def test_sim_feeder_writes_simulated_rows_under_sim_principal(
    db_pool: asyncpg.Pool,
) -> None:
    run_id = UUID("01900000-0000-7000-8000-0000515d0a01")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    clock = deps.clock
    assert isinstance(clock, FakeClock)
    await _seed_run_started(deps.event_store, run_id)

    append = bind_append(deps, observation_store=PostgresObservationStore(db_pool))
    lookup = PostgresRunChannelLookup(db_pool)
    feeder = SimObservationFeeder(
        run_id=run_id,
        started_at=_NOW,
        trace=[TracePoint(0.0, "snr", 7.0), TracePoint(5.0, "snr", 3.0)],
        append_observations=append,
        heartbeat_store=PostgresFeedHeartbeatStore(db_pool),
        clock=clock,
        id_generator=UUIDv7Generator(),
    )

    assert await feeder.drain() == 1  # offset 0 due
    clock.advance(timedelta(seconds=5))
    assert await feeder.drain() == 1  # offset 5 due

    latest = await lookup.read_run_channel_latest(run_id=run_id, channel_name="snr")
    assert latest is not None
    assert latest.value == 3.0
    assert latest.is_simulated is True  # provenance flows through the write path

    # Principal split: every sim row is attributable to the sim principal,
    # distinguishable from any real feeder at the authz / actor_id layer.
    async with db_pool.acquire() as conn:
        actor_ids = await conn.fetch(
            "SELECT DISTINCT actor_id FROM entries_run_observations WHERE run_id = $1", run_id
        )
    assert [r["actor_id"] for r in actor_ids] == [SIM_OBSERVATION_FEEDER_AGENT_ID]


@pytest.mark.integration
async def test_sim_feeder_heartbeat_drives_dead_feeder_stall_gate(
    db_pool: asyncpg.Pool,
) -> None:
    """A drain writes a heartbeat; a fresh heartbeat lets a zero-arrival channel
    stall-flag, while a stale one (feeder stopped + clock past the ceiling)
    defers. The dead-feeder seam the gate review required, end to end."""
    run_id = UUID("01900000-0000-7000-8000-0000515d0b01")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    clock = deps.clock
    assert isinstance(clock, FakeClock)
    await _seed_run_started(deps.event_store, run_id)

    append = bind_append(deps, observation_store=PostgresObservationStore(db_pool))
    lookup = PostgresRunChannelLookup(db_pool)
    feeder = SimObservationFeeder(
        run_id=run_id,
        started_at=_NOW,
        trace=[TracePoint(0.0, "snr", 7.0)],
        append_observations=append,
        heartbeat_store=PostgresFeedHeartbeatStore(db_pool),
        clock=clock,
        id_generator=UUIDv7Generator(),
    )
    await feeder.drain()  # writes a heartbeat (proving the feeder is alive)

    health = await lookup.read_feed_health(run_id=run_id)
    assert health.latest_heartbeat_recorded_at is not None
    hb = health.latest_heartbeat_recorded_at

    # The stall channel never received data: a zero-arrival window.
    window = await lookup.read_run_channel_window(
        run_id=run_id, channel_name="projection_index", since=hb - timedelta(seconds=60)
    )
    assert window.count_since == 0

    # Fresh heartbeat (within the ceiling): the stall rule flags.
    feed_alive_fresh = (hb + timedelta(seconds=10) - hb).total_seconds() <= _FEED_CEILING_SECONDS
    assert feed_alive_fresh is True
    fresh = decide_signal_stall(
        count_since=window.count_since,
        window_seconds=30.0,
        expected_interval=10.0,
        feed_alive=feed_alive_fresh,
        beam_open=True,
    )
    assert fresh.would_flag is True

    # Feeder stopped + clock advanced past the ceiling: heartbeat is stale, so
    # the rule defers (a dead feeder is never read as a calm stall).
    feed_alive_stale = (
        hb + timedelta(seconds=_FEED_CEILING_SECONDS + 1) - hb
    ).total_seconds() <= _FEED_CEILING_SECONDS
    assert feed_alive_stale is False
    stale = decide_signal_stall(
        count_since=window.count_since,
        window_seconds=30.0,
        expected_interval=10.0,
        feed_alive=feed_alive_stale,
        beam_open=True,
    )
    assert stale.would_flag is False
    assert stale.reason == "feed_dead"
