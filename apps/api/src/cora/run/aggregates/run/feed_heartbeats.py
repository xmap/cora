"""Feed-heartbeat entry: append-only feeder-liveness pings.

The write half of the dead-feeder seam
([[project_observation_signal_port_design]] decision F). A feeder runtime
inserts one heartbeat per drain tick (regardless of whether any
observation flowed) so the stall rule can tell a genuinely quiet channel
from a dead feeder. Read side is RunChannelLookup.read_feed_health
(MAX(recorded_at)); the decider derives liveness from the ceiling.

Mirrors the ObservationStore per-category-writer pattern: a typed
dataclass + a category-local Protocol + Postgres / InMemory adapters,
BC-internal (NOT a shared cross-BC port). Append-only INSERT (no UPSERT):
the entries_* table is REVOKEd from UPDATE, and MAX(recorded_at) answers
"newest heartbeat" without mutable state.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class FeedHeartbeat:
    """One feeder-liveness ping for a Run.

    `event_id` is the producer-assigned UUIDv7 dedup key (PK; ON CONFLICT
    DO NOTHING). `source_id` identifies the feeder (a deployment may run
    several). `heartbeat_at` is the producer-asserted ping time (forensic
    only); `recorded_at` (DB DEFAULT now()) is the trusted freshness
    anchor and is not carried on this row.
    """

    event_id: UUID
    run_id: UUID
    source_id: str
    heartbeat_at: datetime


class FeedHeartbeatStore(Protocol):
    """Per-category port for feed-heartbeat writes (BC-internal)."""

    async def append(self, rows: list[FeedHeartbeat]) -> None: ...


_APPEND_SQL = """
INSERT INTO entries_run_feed_heartbeats (
    event_id, run_id, source_id, heartbeat_at
) VALUES ($1, $2, $3, $4)
ON CONFLICT (event_id) DO NOTHING
"""


class PostgresFeedHeartbeatStore:
    """asyncpg-backed `FeedHeartbeatStore` (idempotent on event_id)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, rows: list[FeedHeartbeat]) -> None:
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                _APPEND_SQL,
                [(r.event_id, r.run_id, r.source_id, r.heartbeat_at) for r in rows],
            )


class InMemoryFeedHeartbeatStore:
    """Test / `app_env=test` adapter; dict keyed by event_id for dedup."""

    def __init__(self) -> None:
        self._rows: dict[UUID, FeedHeartbeat] = {}

    async def append(self, rows: list[FeedHeartbeat]) -> None:
        for row in rows:
            self._rows.setdefault(row.event_id, row)

    def all(self) -> list[FeedHeartbeat]:
        return list(self._rows.values())


__all__ = [
    "FeedHeartbeat",
    "FeedHeartbeatStore",
    "InMemoryFeedHeartbeatStore",
    "PostgresFeedHeartbeatStore",
]
