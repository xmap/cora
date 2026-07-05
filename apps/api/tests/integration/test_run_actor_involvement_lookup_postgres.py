"""Integration: RunActorInvolvementProjection + PostgresRunActorInvolvementLookup
against real Postgres (kill-switch K2, the actor-involvement resolver).

The projection unit tests (test_run_actor_involvement_projection.py) mock the
connection, so the actual table, the `status IN ('Running','Held')` in-flight
filter, and the envelope-principal attribution are only exercised here.

Seeds Run lifecycle events directly through PostgresEventStore (the STARTER is
the RunStarted event's ENVELOPE principal_id, not a payload field, so a direct
seed is the faithful way to vary the starter per run without the full
start_run upstream chain), drains the projection worker, then queries through
the adapter.

Pins:
  - runs_driven_by returns the in-flight runs a principal STARTED.
  - A held run is still in-flight (returned); a resumed run returns to
    in-flight; each terminal transition (Completed/Aborted/Stopped/Truncated)
    drops the run from the result while retaining its audit row.
  - Attribution keys on the RunStarted ENVELOPE principal_id: a different
    starter's runs never surface under this principal.
  - A RunStarted with no envelope principal (pre-hook / backfilled) is skipped,
    not attributed.
  - An unknown principal returns [].
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.event_store import NewEvent
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run.adapters import PostgresRunActorInvolvementLookup
from cora.run.projections import RunActorInvolvementProjection

_NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    registry.register(RunActorInvolvementProjection())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _append(
    store: PostgresEventStore,
    *,
    run_id: UUID,
    event_type: str,
    expected_version: int,
    principal_id: UUID | None,
    reason: str | None = None,
    occurred_at: datetime = _NOW,
) -> None:
    payload: dict[str, object] = {"run_id": str(run_id), "occurred_at": occurred_at.isoformat()}
    if reason is not None:
        payload["reason"] = reason
    await store.append(
        "Run",
        run_id,
        expected_version,
        [
            NewEvent(
                event_id=uuid4(),
                event_type=event_type,
                schema_version=1,
                payload=payload,
                occurred_at=occurred_at,
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                metadata={},
                principal_id=principal_id,
            )
        ],
    )


async def _start_run(
    store: PostgresEventStore,
    *,
    run_id: UUID,
    starter: UUID | None,
    occurred_at: datetime = _NOW,
) -> None:
    await _append(
        store,
        run_id=run_id,
        event_type="RunStarted",
        expected_version=0,
        principal_id=starter,
        occurred_at=occurred_at,
    )


@pytest.mark.integration
async def test_unknown_principal_returns_empty(db_pool: asyncpg.Pool) -> None:
    """A principal that started no run drives nothing (the normal post-hoc-agent
    case)."""
    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(uuid4()) == []


@pytest.mark.integration
async def test_started_run_is_driven_by_its_envelope_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """RunStarted attributes the run to its ENVELOPE principal (the starter),
    and a freshly started run is in-flight (Running)."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(starter) == [run_id]


@pytest.mark.integration
async def test_held_run_stays_in_flight(db_pool: asyncpg.Pool) -> None:
    """RunHeld keeps the run in-flight: a revoked principal's HELD runs must
    still be resolvable (they are exactly what the kill-switch holds/keeps held)."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _append(
        store,
        run_id=run_id,
        event_type="RunHeld",
        expected_version=1,
        principal_id=starter,
        reason="beam dropped",
    )
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(starter) == [run_id]


@pytest.mark.integration
async def test_resumed_run_returns_to_in_flight(db_pool: asyncpg.Pool) -> None:
    """Held -> Resumed folds status back to Running; the run stays resolvable."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _append(
        store, run_id=run_id, event_type="RunHeld", expected_version=1, principal_id=starter
    )
    await _append(
        store, run_id=run_id, event_type="RunResumed", expected_version=2, principal_id=starter
    )
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(starter) == [run_id]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("terminal_type", "reason"),
    [
        ("RunCompleted", None),
        ("RunAborted", "operator abort"),
        ("RunStopped", "controlled early stop"),
        ("RunTruncated", "downstream truncation"),
    ],
)
async def test_terminal_run_is_excluded_from_in_flight(
    db_pool: asyncpg.Pool, terminal_type: str, reason: str | None
) -> None:
    """Each terminal transition drops the run from runs_driven_by: a terminal run
    can no longer be held, so the resolver must not return it."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _append(
        store,
        run_id=run_id,
        event_type=terminal_type,
        expected_version=1,
        principal_id=starter,
        reason=reason,
    )
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(starter) == []


@pytest.mark.integration
async def test_terminal_row_retained_for_audit(db_pool: asyncpg.Pool) -> None:
    """A terminal run leaves its involvement row in place (status='Completed'),
    it is only filtered from the in-flight lookup, not deleted."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _append(
        store, run_id=run_id, event_type="RunCompleted", expected_version=1, principal_id=starter
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, involvement_role FROM proj_run_actor_involvement "
            "WHERE principal_id = $1 AND run_id = $2",
            starter,
            run_id,
        )
    assert row is not None
    assert row["status"] == "Completed"
    assert row["involvement_role"] == "starter"


@pytest.mark.integration
async def test_attribution_is_per_starter(db_pool: asyncpg.Pool) -> None:
    """Two principals each start their own run; runs_driven_by returns only the
    caller's own run. Attribution keys on the RunStarted envelope principal."""
    store = PostgresEventStore(db_pool)
    alice = uuid4()
    bob = uuid4()
    alice_run = uuid4()
    bob_run = uuid4()
    await _start_run(store, run_id=alice_run, starter=alice)
    await _start_run(store, run_id=bob_run, starter=bob)
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.runs_driven_by(alice) == [alice_run]
    assert await lookup.runs_driven_by(bob) == [bob_run]


@pytest.mark.integration
async def test_multiple_in_flight_runs_ordered_by_created_at(
    db_pool: asyncpg.Pool,
) -> None:
    """One principal starting several in-flight runs gets them all back, ordered
    by (created_at, run_id). created_at is the RunStarted envelope occurred_at,
    so a run started LATER sorts LAST regardless of its run_id: seed the earliest
    occurred_at on the largest run_id to prove created_at is the primary key, not
    the run_id tiebreak."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_ids = sorted((uuid4() for _ in range(3)), reverse=True)  # descending run_id
    times = [
        datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC),
        datetime(2026, 7, 5, 12, 5, 0, tzinfo=UTC),
        datetime(2026, 7, 5, 12, 10, 0, tzinfo=UTC),
    ]
    for run_id, when in zip(run_ids, times, strict=True):
        await _start_run(store, run_id=run_id, starter=starter, occurred_at=when)
    await _drain(db_pool)

    lookup = PostgresRunActorInvolvementLookup(db_pool)
    got = await lookup.runs_driven_by(starter)
    # Chronological by created_at (earliest first) == the seed order, which is
    # DESCENDING run_id: proves created_at sorts ahead of the run_id tiebreak.
    assert got == run_ids


@pytest.mark.integration
async def test_runstarted_without_envelope_principal_is_skipped(
    db_pool: asyncpg.Pool,
) -> None:
    """A pre-hook / backfilled RunStarted with no envelope principal_id has no
    starter to attribute, so no involvement row is written (no crash, no ghost
    attribution)."""
    store = PostgresEventStore(db_pool)
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=None)
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM proj_run_actor_involvement WHERE run_id = $1", run_id
        )
    assert count == 0


@pytest.mark.integration
async def test_replay_from_zero_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Draining the same stream twice (at-least-once redelivery / rebuild) yields
    exactly one row in its final state: the INSERT's ON CONFLICT DO NOTHING and
    the set-to-constant UPDATEs make apply() idempotent."""
    store = PostgresEventStore(db_pool)
    starter = uuid4()
    run_id = uuid4()
    await _start_run(store, run_id=run_id, starter=starter)
    await _append(
        store, run_id=run_id, event_type="RunHeld", expected_version=1, principal_id=starter
    )
    await _drain(db_pool)
    # Second drain replays the bookmark-tracked stream; without idempotency this
    # would double-insert or clobber. Reset the bookmark to force a full replay.
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE projection_bookmarks SET last_transaction_id = '0'::xid8, last_position = 0 "
            "WHERE name = 'proj_run_actor_involvement'"
        )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status FROM proj_run_actor_involvement WHERE run_id = $1", run_id
        )
    assert len(rows) == 1
    assert rows[0]["status"] == "Held"


@pytest.mark.integration
async def test_terminal_event_without_run_started_is_a_harmless_noop(
    db_pool: asyncpg.Pool,
) -> None:
    """A lifecycle event for a run that has no involvement row (its RunStarted was
    skipped for a None principal, or has not yet been projected) updates zero rows:
    no crash, no ghost row."""
    store = PostgresEventStore(db_pool)
    run_id = uuid4()
    # RunStarted with no envelope principal -> no row; a following terminal event
    # must not resurrect one.
    await _start_run(store, run_id=run_id, starter=None)
    await _append(
        store, run_id=run_id, event_type="RunCompleted", expected_version=1, principal_id=None
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM proj_run_actor_involvement WHERE run_id = $1", run_id
        )
    assert count == 0
