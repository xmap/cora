"""Integration: ensure_bookmarks seeds a Reaction's bookmark so the worker path
can advance it (the subscriber-bookmark gap fix).

Reactions (side-effecting subscribers) own no proj_* table and thus no migration,
so nothing seeds their projection_bookmarks row. Before the fix, a Reaction's
first advance through the worker raised MissingBookmarkError forever and it never
fired. This test reproduces that (advance raises without a bookmark) and pins the
fix (after ensure_bookmarks the same advance succeeds and the Reaction sees its
event).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from cora.infrastructure.projection.bookmark import (
    MissingBookmarkError,
    ensure_bookmarks,
)
from cora.infrastructure.projection.handler import ConnectionLike
from cora.infrastructure.projection.worker import advance_subscriber_once

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


class _RecordingReaction:
    """Minimal Reaction: no proj_* table, no migration (the bug's shape).

    Captures the events it is handed so the test can assert the worker path
    actually delivered them once a bookmark exists.
    """

    name = "test_ensure_bookmarks_reaction"
    subscribed_event_types = frozenset({"EnsureBookmarksProbeEvent"})
    batch_size = 1

    def __init__(self) -> None:
        self.seen: list[StoredEvent] = []

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        _ = conn
        self.seen.append(event)


async def _append_probe(store: PostgresEventStore) -> None:
    await store.append(
        "TestStream",
        uuid4(),
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="EnsureBookmarksProbeEvent",
                schema_version=1,
                payload={"k": "v"},
                occurred_at=_NOW,
                correlation_id=uuid4(),
                causation_id=None,
                metadata={},
                principal_id=uuid4(),
            )
        ],
    )


@pytest.mark.integration
async def test_advance_without_bookmark_raises_missing_bookmark(db_pool: asyncpg.Pool) -> None:
    """Reproduce the bug: a Reaction with no seeded bookmark cannot advance."""
    reaction = _RecordingReaction()
    with pytest.raises(MissingBookmarkError):
        await advance_subscriber_once(db_pool, reaction)


@pytest.mark.integration
async def test_ensure_bookmarks_lets_the_reaction_advance(db_pool: asyncpg.Pool) -> None:
    """After ensure_bookmarks seeds the row, the same worker-path advance delivers
    the event to the Reaction."""
    store = PostgresEventStore(db_pool)
    reaction = _RecordingReaction()
    await _append_probe(store)

    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    processed = await advance_subscriber_once(db_pool, reaction)

    assert processed == 1
    assert len(reaction.seen) == 1
    assert reaction.seen[0].event_type == "EnsureBookmarksProbeEvent"


@pytest.mark.integration
async def test_ensure_bookmarks_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Calling ensure_bookmarks twice (restart) does not reset an advanced cursor:
    the second call is a no-op via ON CONFLICT DO NOTHING."""
    store = PostgresEventStore(db_pool)
    reaction = _RecordingReaction()
    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    await _append_probe(store)
    assert await advance_subscriber_once(db_pool, reaction) == 1

    # Second ensure (as on a restart) must not rewind the bookmark to zero.
    await ensure_bookmarks(db_pool, frozenset({reaction.name}))
    # No new events -> nothing to process; if the cursor had reset, the probe
    # would be re-delivered and this would be 1.
    assert await advance_subscriber_once(db_pool, reaction) == 0


@pytest.mark.integration
async def test_lifespan_seeds_registered_reaction_bookmark(db_pool: asyncpg.Pool) -> None:
    """The production wiring: projection_worker_lifespan seeds a bookmark for every
    registered subscriber before the worker starts, so a bookmark-less Reaction is
    no longer stranded. Pins the fix at the real lifespan seam (not just the helper),
    so a future refactor that drops the ensure step regresses here."""
    from cora.infrastructure.config import Settings
    from cora.infrastructure.projection import ProjectionRegistry
    from cora.infrastructure.projection.bookmark import read_bookmark
    from cora.infrastructure.projection.lifespan import projection_worker_lifespan
    from tests.integration._helpers import build_postgres_deps

    reaction = _RecordingReaction()
    registry = ProjectionRegistry()
    registry.register(reaction)
    deps = build_postgres_deps(db_pool, now=_NOW)
    settings = Settings()  # type: ignore[call-arg]

    async def _read_cursor() -> tuple[int, int]:
        async with db_pool.acquire() as conn, conn.transaction():
            return await read_bookmark(conn, reaction.name)

    async with projection_worker_lifespan(deps, registry, settings):
        # Inside the context the worker is running; the bookmark MUST exist (the
        # ensure step ran before the worker spawned). read_bookmark raises
        # MissingBookmarkError if the row is absent.
        cursor = await _read_cursor()
    assert cursor == (0, 0)
