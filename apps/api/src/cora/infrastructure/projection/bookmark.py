"""Bookmark read/write SQL helpers.

The worker's advance loop calls these inside its transaction:

  1. `read_bookmark(conn, name)` -> `(last_transaction_id, last_position)`
     locks the bookmark row FOR UPDATE so concurrent workers (when
     deferred multi-worker arrives) won't double-advance.
  2. `write_bookmark(conn, name, ...)` updates the bookmark and
     resets the failure-tracking columns; commits with the same
     transaction as the projection writes for atomic at-least-once
     delivery.
  3. `write_bookmark_failure(pool, name, error_message)` updates ONLY
     the failure columns in a SEPARATE small transaction (NOT the
     advance-loop transaction, which is rolling back). The bookmark
     position itself stays put so retry semantics are preserved.

`projection_bookmarks` carries four observability columns
(`last_event_recorded_at`, `last_error_at`, `last_error_message`,
`consecutive_failures`). Success path resets failure columns to NULL
+ counter to 0 atomically with the position advance; failure path
increments the counter and records the error message in its own
small transaction. Pre-positions for the full read-side observability
surface (admin endpoint + lag sampler + OTel) which stays deferred
until the trigger fires.

Bookmark rows for PROJECTIONS are created by their per-projection
migration (`INSERT INTO projection_bookmarks (name) VALUES (...) ON
CONFLICT DO NOTHING`). Registering a projection whose migration never
landed fails loudly at first advance (`test_projection_table_match`
also enforces the migration exists), which is the behavior we want.

REACTIONS (side-effecting subscribers) own no `proj_*` table and thus
no migration, so nothing would seed their bookmark. `ensure_bookmarks`
closes that gap: the lifespan calls it once for every registered
subscriber before the worker starts, creating any missing row
idempotently. Without it a reaction's first advance raises
`MissingBookmarkError` forever inside the worker's backoff loop and the
reaction never fires.

A reaction's new row starts at the current head rather than at zero, so
enabling one is a go-live and not a replay of everything that already
happened. See `ensure_bookmarks` for why the two kinds differ and why
head is a transaction-id watermark rather than a max position.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime

import asyncpg

from cora.infrastructure.projection.handler import ConnectionLike

# Bound the bookmark UPDATE size. Operators see error class + first
# part of message; full traceback goes to OTel spans when the full
# observability surface ships.
_ERROR_MESSAGE_MAX_CHARS = 500

_READ_BOOKMARK_SQL = """
SELECT last_transaction_id::text AS last_tx, last_position
FROM projection_bookmarks
WHERE name = $1
FOR UPDATE
"""
# `last_transaction_id::text` for the same reason as `events`: asyncpg
# 0.31 has no built-in xid8 OUTPUT codec, so we cast and parse to int.

_WRITE_BOOKMARK_SQL = """
UPDATE projection_bookmarks
SET last_transaction_id    = $2::xid8,
    last_position          = $3,
    last_event_recorded_at = $4,
    last_error_at          = NULL,
    last_error_message     = NULL,
    consecutive_failures   = 0,
    updated_at             = now()
WHERE name = $1
"""

_WRITE_BOOKMARK_FAILURE_SQL = """
UPDATE projection_bookmarks
SET last_error_at        = now(),
    last_error_message   = $2,
    consecutive_failures = consecutive_failures + 1,
    updated_at           = now()
WHERE name = $1
"""

_ENSURE_BOOKMARK_SQL = """
INSERT INTO projection_bookmarks (name)
VALUES ($1)
ON CONFLICT (name) DO NOTHING
"""

_ENSURE_REACTION_BOOKMARK_SQL = """
INSERT INTO projection_bookmarks (name, last_transaction_id, last_position)
VALUES ($1, pg_snapshot_xmin(pg_current_snapshot()), 0)
ON CONFLICT (name) DO NOTHING
"""

_PROJECTION_NAME_PREFIX = "proj_"


class MissingBookmarkError(Exception):
    """No bookmark row exists for the given projection name. Indicates
    the projection's migration didn't land (or its `INSERT INTO
    projection_bookmarks` statement was missed)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"No projection_bookmarks row for {name!r}. The projection's "
            "migration must include an `INSERT INTO projection_bookmarks "
            "(name) VALUES (...) ON CONFLICT DO NOTHING` statement."
        )
        self.name = name


async def read_bookmark(
    conn: ConnectionLike,
    name: str,
) -> tuple[int, int]:
    """Read `(last_transaction_id, last_position)` for the projection.

    Locks the row FOR UPDATE; caller is responsible for the surrounding
    transaction. Raises `MissingBookmarkError` if the row doesn't exist.
    """
    row = await conn.fetchrow(_READ_BOOKMARK_SQL, name)
    if row is None:
        raise MissingBookmarkError(name)
    return int(row["last_tx"]), int(row["last_position"])


async def write_bookmark(
    conn: ConnectionLike,
    name: str,
    *,
    last_transaction_id: int,
    last_position: int,
    last_event_recorded_at: datetime,
) -> None:
    """Update the bookmark to the new (last_tx, last_pos) cursor and
    reset failure-tracking columns.

    Called inside the advance-loop transaction; the position advance
    + failure-reset commit together with the projection writes for
    atomic at-least-once delivery + observability consistency.
    """
    await conn.execute(
        _WRITE_BOOKMARK_SQL,
        name,
        last_transaction_id,
        last_position,
        last_event_recorded_at,
    )


async def write_bookmark_failure(
    pool: asyncpg.Pool,
    name: str,
    *,
    error_message: str,
) -> None:
    """Record an advance-loop failure in a SEPARATE small transaction.

    Observability hook called from the advance-loop exception
    handler AFTER the failed batch has rolled back. Increments
    `consecutive_failures` and records `last_error_at` +
    `last_error_message`. Does NOT touch `last_transaction_id` or
    `last_position`, so retry semantics are preserved by leaving
    the cursor where it was.

    Truncates `error_message` to 500 chars to bound bookmark UPDATE
    size. If this UPDATE itself fails, the worker swallows that loss
    silently: we already failed once; the operator's signal is the
    log + (eventually) OTel span on the original failure.
    """
    truncated = error_message[:_ERROR_MESSAGE_MAX_CHARS]
    async with pool.acquire() as conn:
        await conn.execute(_WRITE_BOOKMARK_FAILURE_SQL, name, truncated)


async def ensure_bookmarks(
    pool: asyncpg.Pool,
    names: frozenset[str],
    *,
    reactions_at_head: bool = True,
) -> None:
    """Idempotently create a bookmark row for each given subscriber name.

    Called once at worker startup for every registered subscriber. For a
    PROJECTION the row already exists (its migration seeded it), so the INSERT is
    a no-op via `ON CONFLICT DO NOTHING`. For a REACTION (no table, no migration)
    this creates the otherwise-missing row so its first advance can read a cursor
    instead of raising `MissingBookmarkError` forever. Ordered by name for a
    deterministic write sequence.

    A reaction's new row starts at the CURRENT HEAD, not at zero, and the
    difference is the whole point of this function having two branches.

    A projection must see all history: its `proj_*` table is a fold of the
    entire stream, so starting anywhere but zero yields a read model missing
    everything before it. A reaction must not. It has side effects in the
    world, so replaying history means re-performing it: buying LLM calls,
    writing Decisions, calling out. Enabling a reaction on an existing
    deployment would otherwise be a silent backfill rather than a
    go-live. Measured on 2-BM's pilot record, turning the LLM subscribers
    on for the first time would have fired them at 674 already-finished
    Runs before they saw a single new one, and appended every verdict to a
    record that cannot be edited.

    The two kinds are structurally identical Protocols, so the discriminator
    is the registered name: a projection is named `proj_<table>` (pinned by
    `test_projection_table_match` and `test_projection_table_bc_prefix`),
    a reaction is not.

    HEAD is `pg_snapshot_xmin(pg_current_snapshot())` with position 0, the
    same watermark the record exporter takes, and NOT `max(position)`.
    Positions come from a sequence that advances on rolled-back
    transactions and does not order commits, so a bookmark set past a
    transaction still in flight would skip its events forever once it
    committed. Seeding at xmin instead errs the other way: a handful of
    events mid-commit at seed time may be delivered. That is the safe
    direction, because reactions are already at-least-once and idempotent
    by construction (deterministic UUIDv5 stream ids, `expected_version=0`,
    `ConcurrencyError` treated as a no-op), while a skipped event is
    silently gone.

    Replaying history on purpose stays a separate operator gesture, and
    `reactions_at_head=False` is the seam it will use: it seeds a reaction
    at the origin so the worker walks the whole stream. Callers pass it
    only when replaying is the intent, never to make a test convenient,
    because the two are indistinguishable afterwards. This function exists
    to keep the replay from happening by accident.
    """
    async with pool.acquire() as conn:
        for name in sorted(names):
            at_origin = name.startswith(_PROJECTION_NAME_PREFIX) or not reactions_at_head
            if at_origin:
                await conn.execute(_ENSURE_BOOKMARK_SQL, name)
            else:
                await conn.execute(_ENSURE_REACTION_BOOKMARK_SQL, name)


__all__ = [
    "MissingBookmarkError",
    "ensure_bookmarks",
    "read_bookmark",
    "write_bookmark",
    "write_bookmark_failure",
]
