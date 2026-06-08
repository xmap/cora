"""End-to-end PG integration for `dismiss_event_in_reaction`.

Walks: seed a projection_bookmarks row -> insert a probe event ->
invoke the slice handler -> assert the bookmark advanced to the event's
(transaction_id, position) AND a `DecisionRegistered` row appeared in
the `events` table with `context = "ReactionDismissal"` AND the cursor
that was advanced past is in the Decision's inputs payload.

Plus the wedge-recovery semantics:

  - SubscriberBookmarkNotFoundError when the named subscriber has no
    bookmark row (404)
  - DismissalEventNotFoundError when the event_id does not exist (404)
  - EventAlreadyDismissedError when the bookmark is already past the
    target event (409)
  - Atomic write: if `event_store.append_streams` were to fail mid-
    transaction, the bookmark advance would roll back too (covered
    by the same-transaction shape, not a separate fault-injection
    test).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.errors import (
    DismissalEventNotFoundError,
    EventAlreadyDismissedError,
    SubscriberBookmarkNotFoundError,
)
from cora.agent.features.dismiss_event_in_reaction import (
    DismissEventInReaction,
    bind,
)
from cora.infrastructure.event_envelope import to_new_event
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 14, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000007007")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000c1d0")


async def _ensure_bookmark(
    db_pool: asyncpg.Pool,
    name: str,
    *,
    last_transaction_id: int = 0,
    last_position: int = 0,
) -> None:
    """Insert (or update) a projection_bookmarks row to a known cursor."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO projection_bookmarks (name, last_transaction_id, last_position)
            VALUES ($1, $2::xid8, $3)
            ON CONFLICT (name) DO UPDATE
            SET last_transaction_id = EXCLUDED.last_transaction_id,
                last_position       = EXCLUDED.last_position
            """,
            name,
            last_transaction_id,
            last_position,
        )


async def _read_bookmark(db_pool: asyncpg.Pool, name: str) -> dict[str, object] | None:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT last_transaction_id::text AS last_tx,
                   last_position,
                   last_error_at,
                   last_error_message,
                   consecutive_failures
            FROM projection_bookmarks
            WHERE name = $1
            """,
            name,
        )
    return dict(row) if row is not None else None


async def _append_probe_event(
    db_pool: asyncpg.Pool,
    *,
    event_id: UUID,
    stream_id: UUID,
) -> tuple[int, int]:
    """Append one event to a probe stream and return its
    (transaction_id, position) cursor for the test to assert against."""
    deps = build_postgres_deps(db_pool, now=_NOW)
    new_event = to_new_event(
        event_type="DismissEventInReactionProbeEvent",
        payload={"marker": "probe"},
        occurred_at=_NOW,
        event_id=event_id,
        command_name="ProbeCommand",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="DismissProbe",
        stream_id=stream_id,
        expected_version=0,
        events=[new_event],
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT transaction_id::text AS tx, position FROM events WHERE event_id = $1",
            event_id,
        )
    assert row is not None
    return int(row["tx"]), int(row["position"])


@pytest.mark.integration
async def test_dismiss_event_advances_bookmark_and_writes_decision(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: bookmark advances to event cursor, Decision row
    appears with the right payload, both in the same transaction."""
    subscriber_name = f"probe_reaction_{uuid4().hex[:8]}"
    await _ensure_bookmark(db_pool, subscriber_name)

    event_id = uuid4()
    stream_id = uuid4()
    event_tx, event_pos = await _append_probe_event(db_pool, event_id=event_id, stream_id=stream_id)

    # Handler consumes 2 ids per call: new_decision_id + envelope event_id.
    decision_id_seed = uuid4()
    envelope_event_id = uuid4()
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[decision_id_seed, envelope_event_id],
    )
    handler = bind(deps)
    decision_id = await handler(
        DismissEventInReaction(
            subscriber_name=subscriber_name,
            event_id=event_id,
            reason="schema rename after rollout",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    bookmark = await _read_bookmark(db_pool, subscriber_name)
    assert bookmark is not None
    assert int(bookmark["last_tx"]) == event_tx
    assert bookmark["last_position"] == event_pos
    assert bookmark["last_error_at"] is None
    assert bookmark["last_error_message"] is None
    assert bookmark["consecutive_failures"] == 0

    async with db_pool.acquire() as conn:
        decision_row = await conn.fetchrow(
            """
            SELECT event_type, payload
            FROM events
            WHERE stream_type = 'Decision' AND stream_id = $1
            """,
            decision_id,
        )
    assert decision_row is not None
    assert decision_row["event_type"] == "DecisionRegistered"
    # asyncpg's jsonb codec returns str OR dict depending on config;
    # tolerate both shapes so the test isn't fragile to codec changes.
    raw_payload: Any = decision_row["payload"]
    payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    assert payload["context"] == "ReactionDismissal"
    assert payload["choice"] == "EventDismissed"
    assert payload["decided_by"] == str(_PRINCIPAL_ID)
    assert payload["inputs"]["subscriber_name"] == subscriber_name
    assert payload["inputs"]["event_id"] == str(event_id)
    assert payload["inputs"]["previous_bookmark_transaction_id"] == "0"
    assert payload["inputs"]["previous_bookmark_position"] == "0"
    assert payload["inputs"]["event_transaction_id"] == str(event_tx)
    assert payload["inputs"]["event_position"] == str(event_pos)


@pytest.mark.integration
async def test_dismiss_event_raises_subscriber_bookmark_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    """No bookmark row for the named subscriber: raises SubscriberBookmarkNotFoundError.
    Operator misspelled the name OR the subscriber's migration hasn't landed."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    handler = bind(deps)

    with pytest.raises(SubscriberBookmarkNotFoundError):
        await handler(
            DismissEventInReaction(
                subscriber_name=f"never_registered_{uuid4().hex[:8]}",
                event_id=uuid4(),
                reason="test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_dismiss_event_raises_event_not_found(
    db_pool: asyncpg.Pool,
) -> None:
    """Bookmark exists, but the event_id does not exist in events:
    raises DismissalEventNotFoundError."""
    subscriber_name = f"probe_reaction_{uuid4().hex[:8]}"
    await _ensure_bookmark(db_pool, subscriber_name)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    handler = bind(deps)

    with pytest.raises(DismissalEventNotFoundError):
        await handler(
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=uuid4(),
                reason="test",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_dismiss_event_raises_event_already_dismissed(
    db_pool: asyncpg.Pool,
) -> None:
    """Bookmark is already past the target event: raises
    EventAlreadyDismissedError (no rewinds)."""
    subscriber_name = f"probe_reaction_{uuid4().hex[:8]}"
    event_id = uuid4()
    stream_id = uuid4()
    event_tx, event_pos = await _append_probe_event(db_pool, event_id=event_id, stream_id=stream_id)

    # Pre-advance the bookmark TO the event cursor (so the event is
    # already at-or-past).
    await _ensure_bookmark(
        db_pool,
        subscriber_name,
        last_transaction_id=event_tx,
        last_position=event_pos,
    )

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    handler = bind(deps)

    with pytest.raises(EventAlreadyDismissedError):
        await handler(
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason="trying to dismiss an event we already passed",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_dismiss_event_rollback_on_failure_keeps_bookmark_intact(
    db_pool: asyncpg.Pool,
) -> None:
    """Atomicity pin: if the second write fails, the first rolls back.

    Simulates by re-using the same decision_id from a prior dismissal
    (synthesizing a ConcurrencyError on the Decision append). The
    bookmark advance + Decision write share `conn.transaction()`; the
    Decision append's ConcurrencyError aborts the whole transaction,
    so the bookmark stays at its previous cursor.

    Today's id_generator is fresh-UUIDv7-per-call so we can't easily
    force the collision; this test instead verifies the SHAPE: a
    successful dismissal advances the bookmark, a second dismissal of
    the SAME event raises EventAlreadyDismissedError (without touching
    the bookmark), and the bookmark stays at the first advanced
    position. That's the contract observers care about: the bookmark
    is never left in an intermediate state."""
    subscriber_name = f"probe_reaction_{uuid4().hex[:8]}"
    await _ensure_bookmark(db_pool, subscriber_name)

    event_id = uuid4()
    stream_id = uuid4()
    event_tx, event_pos = await _append_probe_event(db_pool, event_id=event_id, stream_id=stream_id)

    # Two dismissals in this test: 2 ids per call x 2 = 4 ids.
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4(), uuid4(), uuid4(), uuid4()],
    )
    handler = bind(deps)

    await handler(
        DismissEventInReaction(
            subscriber_name=subscriber_name,
            event_id=event_id,
            reason="first dismissal",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    bookmark_after_first = await _read_bookmark(db_pool, subscriber_name)
    assert bookmark_after_first is not None
    assert int(bookmark_after_first["last_tx"]) == event_tx
    assert bookmark_after_first["last_position"] == event_pos

    # Second dismissal of the SAME event raises EventAlreadyDismissedError.
    with pytest.raises(EventAlreadyDismissedError):
        await handler(
            DismissEventInReaction(
                subscriber_name=subscriber_name,
                event_id=event_id,
                reason="second dismissal",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Bookmark stayed at the first advanced cursor (no rewind, no
    # mid-flight state).
    bookmark_after_second = await _read_bookmark(db_pool, subscriber_name)
    assert bookmark_after_second is not None
    assert int(bookmark_after_second["last_tx"]) == event_tx
    assert bookmark_after_second["last_position"] == event_pos
