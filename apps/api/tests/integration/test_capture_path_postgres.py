"""Integration: the `run_capture_path` PII vault against real Postgres.

Mirrors `test_feed_heartbeats_postgres.py`'s shape: exercise
`PostgresCapturePathStore` directly against the migrated table, no
handler involved (this store is a plain composition-root dependency,
not wrapped by a command). Also confirms the RLS posture the init
migration declares: `cora_app` (the role `db_pool` connects as in
tests) can read and write; FORCE ROW LEVEL SECURITY is asserted at the
catalog level since there is no second role easily reachable in-test to
prove a bypass attempt fails.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.run.aggregates.run import PostgresCapturePathStore

_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)


@pytest.mark.integration
async def test_upsert_then_get_roundtrips_through_postgres(db_pool: asyncpg.Pool) -> None:
    store = PostgresCapturePathStore(db_pool)
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        observed_path="/data/2026-01-Smith-12345/scan_001.h5",
        observed_at=_NOW,
        created_at=_NOW,
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.run_id == run_id
    assert row.observed_path == "/data/2026-01-Smith-12345/scan_001.h5"
    assert row.observed_at == _NOW


@pytest.mark.integration
async def test_get_absent_run_id_returns_none(db_pool: asyncpg.Pool) -> None:
    store = PostgresCapturePathStore(db_pool)
    assert await store.get(uuid4()) is None


@pytest.mark.integration
async def test_upsert_is_idempotent_on_run_id(db_pool: asyncpg.Pool) -> None:
    """A retry (same run_id, e.g. after a transient failure) overwrites
    rather than duplicating: `run_id` is the PRIMARY KEY, and
    `ON CONFLICT (run_id) DO UPDATE` is the whole point of the vault
    being mutable, not append-only."""
    store = PostgresCapturePathStore(db_pool)
    run_id = uuid4()
    await store.upsert(
        run_id=run_id, observed_path="/data/first.h5", observed_at=_NOW, created_at=_NOW
    )
    await store.upsert(
        run_id=run_id, observed_path="/data/second.h5", observed_at=_NOW, created_at=_NOW
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM run_capture_path WHERE run_id = $1", run_id
        )
    assert count == 1
    row = await store.get(run_id)
    assert row is not None
    assert row.observed_path == "/data/second.h5"


@pytest.mark.integration
async def test_table_has_force_row_level_security_enabled(db_pool: asyncpg.Pool) -> None:
    """Defense-in-depth check on the migration itself: FORCE (not just
    ENABLE) means even the table-owner role goes through policy,
    mirroring `actor_profile`'s identical posture."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = $1",
            "run_capture_path",
        )
    assert row is not None
    assert row["relrowsecurity"] is True
    assert row["relforcerowsecurity"] is True


@pytest.mark.integration
async def test_observed_path_length_constraint_rejects_an_oversized_value(
    db_pool: asyncpg.Pool,
) -> None:
    """Defense-in-depth on the same fact the application-layer
    truncation guard checks (NELM=512 on the real PV, 511 usable
    chars): the CHECK constraint is a second, independent backstop."""
    store = PostgresCapturePathStore(db_pool)
    with pytest.raises(asyncpg.CheckViolationError):
        await store.upsert(
            run_id=uuid4(),
            observed_path="a" * 512,
            observed_at=_NOW,
            created_at=_NOW,
        )
