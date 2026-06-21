"""Integration: feed-heartbeat write + read_feed_health against Postgres.

Append-only INSERT (no UPSERT) into entries_run_feed_heartbeats, read
back as MAX(recorded_at) via PostgresRunChannelLookup.read_feed_health.
recorded_at is the real DB DEFAULT now(); the newest insert wins.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.run.adapters import PostgresRunChannelLookup
from cora.run.aggregates.run import FeedHeartbeat, PostgresFeedHeartbeatStore

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def _beat(run_id: UUID, source: str = "epics") -> FeedHeartbeat:
    return FeedHeartbeat(event_id=uuid4(), run_id=run_id, source_id=source, heartbeat_at=_NOW)


async def _recorded_at(pool: asyncpg.Pool, event_id: UUID) -> datetime:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT recorded_at FROM entries_run_feed_heartbeats WHERE event_id = $1", event_id
        )


@pytest.mark.integration
async def test_read_feed_health_returns_none_when_no_heartbeat(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresRunChannelLookup(db_pool)
    health = await lookup.read_feed_health(run_id=uuid4())
    assert health.latest_heartbeat_recorded_at is None


@pytest.mark.integration
async def test_read_feed_health_returns_newest_across_sources(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresFeedHeartbeatStore(db_pool)
    lookup = PostgresRunChannelLookup(db_pool)

    await store.append([_beat(run_id, "epics")])
    await asyncio.sleep(0.01)
    newest = _beat(run_id, "tomostream")
    await store.append([newest])

    health = await lookup.read_feed_health(run_id=run_id)
    assert health.latest_heartbeat_recorded_at == await _recorded_at(db_pool, newest.event_id)


@pytest.mark.integration
async def test_heartbeat_append_is_idempotent_on_event_id(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresFeedHeartbeatStore(db_pool)
    beat = _beat(run_id)
    await store.append([beat])
    await store.append([beat])  # retry, same event_id
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM entries_run_feed_heartbeats WHERE run_id = $1", run_id
        )
    assert count == 1
