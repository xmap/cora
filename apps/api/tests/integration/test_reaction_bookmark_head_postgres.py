"""Enabling a reaction is a go-live, not a replay of everything before it.

`ensure_bookmarks` seeds a REACTION's new bookmark at the current head
and a PROJECTION's at zero. The asymmetry is deliberate: a projection
folds all history into its read model, while a reaction has side
effects in the world, so replaying history means re-performing it.

These pin the three properties that make the seeding safe:

  - a reaction does not see what already happened when it is enabled
  - it does see everything from then on
  - a restart does not re-seed, so nothing is skipped across downtime

The third is the one that would hurt most quietly. Re-seeding on every
boot would silently drop every event that arrived while the process was
down, and the bookmark would look perfectly healthy afterwards.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from cora.infrastructure.projection.bookmark import ensure_bookmarks
from cora.infrastructure.projection.handler import ConnectionLike
from cora.infrastructure.projection.worker import advance_subscriber_once

_EVENT_TYPE = "ReactionHeadSeedTestEvent"
_PRINCIPAL = UUID("01900000-0000-7000-8000-00000000ee01")


class _CapturingReaction:
    """Test-only reaction. The name carries no `proj_` prefix, which is
    what marks it a reaction to `ensure_bookmarks`."""

    name = "reaction_head_seed_probe"
    subscribed_event_types = frozenset({_EVENT_TYPE})

    def __init__(self) -> None:
        self.captured: list[StoredEvent] = []

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        _ = conn
        self.captured.append(event)


def _make_event() -> NewEvent:
    return NewEvent(
        event_id=uuid4(),
        event_type=_EVENT_TYPE,
        schema_version=1,
        payload={"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=_PRINCIPAL,
    )


async def _append_one(db_pool: asyncpg.Pool) -> None:
    store = PostgresEventStore(db_pool)
    await store.append("TestStream", uuid4(), 0, [_make_event()])


async def _read_position(db_pool: asyncpg.Pool, name: str) -> tuple[int, int]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT last_transaction_id::text AS tx, last_position AS pos
            FROM projection_bookmarks WHERE name = $1
            """,
            name,
        )
    assert row is not None
    return int(row["tx"]), int(row["pos"])


@pytest.mark.integration
async def test_new_reaction_bookmark_skips_events_that_predate_it(
    db_pool: asyncpg.Pool,
) -> None:
    reaction = _CapturingReaction()
    await _append_one(db_pool)

    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    processed = await advance_subscriber_once(db_pool, reaction, batch_size=10)

    assert processed == 0
    assert reaction.captured == []


@pytest.mark.integration
async def test_new_reaction_bookmark_still_receives_later_events(
    db_pool: asyncpg.Pool,
) -> None:
    reaction = _CapturingReaction()
    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    await _append_one(db_pool)

    processed = await advance_subscriber_once(db_pool, reaction, batch_size=10)

    assert processed == 1
    assert len(reaction.captured) == 1


@pytest.mark.integration
async def test_ensure_bookmarks_does_not_reseed_an_existing_reaction(
    db_pool: asyncpg.Pool,
) -> None:
    """A restart must not skip what arrived while the process was down."""
    reaction = _CapturingReaction()
    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    before = await _read_position(db_pool, reaction.name)

    await _append_one(db_pool)
    await ensure_bookmarks(db_pool, frozenset({reaction.name}))

    assert await _read_position(db_pool, reaction.name) == before
    assert await advance_subscriber_once(db_pool, reaction, batch_size=10) == 1


@pytest.mark.integration
async def test_new_projection_bookmark_starts_at_zero(
    db_pool: asyncpg.Pool,
) -> None:
    """A projection folds all history, so its seed stays at the origin.

    Its row normally comes from its own migration; this pins that the
    fallback insert agrees with the migration rather than quietly
    starting the read model partway through the stream.
    """
    name = "proj_reaction_head_seed_probe"
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM projection_bookmarks WHERE name = $1", name)

    await ensure_bookmarks(db_pool, frozenset({name}))

    assert await _read_position(db_pool, name) == (0, 0)
