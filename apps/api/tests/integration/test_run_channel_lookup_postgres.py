"""Integration: PostgresRunChannelLookup against real Postgres.

Seeds rows through PostgresObservationStore (so recorded_at is the real
DB DEFAULT now()), then exercises the two read methods. The window
assertions key on the real DB-assigned recorded_at (read back from the
table) so the strict `since` floor is deterministic, not clock-guessed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.run.adapters import PostgresRunChannelLookup
from cora.run.aggregates.run import Observation, PostgresObservationStore

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def _obs(run_id: UUID, channel: str, value: float, *, is_simulated: bool = False) -> Observation:
    return Observation(
        event_id=uuid4(),
        run_id=run_id,
        logbook_id=uuid4(),
        actor_id=uuid4(),
        command_name="AppendObservations",
        channel_name=channel,
        value=value,
        units=None,
        sampling_procedure="monitor",
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
        is_simulated=is_simulated,
    )


async def _recorded_at(pool: asyncpg.Pool, event_id: UUID) -> datetime:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT recorded_at FROM entries_run_observations WHERE event_id = $1", event_id
        )


@pytest.mark.integration
async def test_latest_returns_none_for_unknown_channel(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresRunChannelLookup(db_pool)
    got = await lookup.read_run_channel_latest(run_id=uuid4(), channel_name="snr")
    assert got is None


@pytest.mark.integration
async def test_latest_returns_most_recent_by_recorded_at(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    lookup = PostgresRunChannelLookup(db_pool)

    first = _obs(run_id, "snr", 4.0)
    await store.append([first])
    await asyncio.sleep(0.01)  # guarantee a strictly later recorded_at
    second = _obs(run_id, "snr", 9.0, is_simulated=True)
    await store.append([second])

    latest = await lookup.read_run_channel_latest(run_id=run_id, channel_name="snr")
    assert latest is not None
    assert latest.value == 9.0
    assert latest.is_simulated is True
    assert latest.recorded_at == await _recorded_at(db_pool, second.event_id)


@pytest.mark.integration
async def test_window_counts_arrivals_after_recorded_at_floor(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    lookup = PostgresRunChannelLookup(db_pool)

    first = _obs(run_id, "projection_index", 1.0)
    await store.append([first])
    await asyncio.sleep(0.01)
    second = _obs(run_id, "projection_index", 2.0)
    await store.append([second])

    first_recorded = await _recorded_at(db_pool, first.event_id)
    second_recorded = await _recorded_at(db_pool, second.event_id)

    # Floor before everything: both counted.
    full = await lookup.read_run_channel_window(
        run_id=run_id, channel_name="projection_index", since=first_recorded - timedelta(seconds=1)
    )
    assert full.count_since == 2
    assert full.first_recorded_at == first_recorded
    assert full.latest_recorded_at == second_recorded

    # Floor at the first row's recorded_at: strict > excludes it, counts only the second.
    partial = await lookup.read_run_channel_window(
        run_id=run_id, channel_name="projection_index", since=first_recorded
    )
    assert partial.count_since == 1
    assert partial.first_recorded_at == second_recorded

    # Floor at/after the latest: empty window, zero-count signal.
    empty = await lookup.read_run_channel_window(
        run_id=run_id, channel_name="projection_index", since=second_recorded
    )
    assert empty.count_since == 0
    assert empty.first_recorded_at is None
    assert empty.is_simulated_window is False


@pytest.mark.integration
async def test_window_or_folds_is_simulated(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    lookup = PostgresRunChannelLookup(db_pool)

    await store.append([_obs(run_id, "snr", 1.0, is_simulated=False)])
    await store.append([_obs(run_id, "snr", 2.0, is_simulated=True)])

    signal = await lookup.read_run_channel_window(
        run_id=run_id, channel_name="snr", since=_NOW - timedelta(days=1)
    )
    assert signal.count_since == 2
    assert signal.is_simulated_window is True
