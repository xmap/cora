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

from datetime import UTC, datetime, timedelta
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
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.run_id == run_id
    assert row.observed_path == "/data/2026-01-Smith-12345/scan_001.h5"
    assert row.observed_at == _NOW


@pytest.mark.integration
async def test_get_absent_run_id_returns_none(db_pool: asyncpg.Pool) -> None:
    store = PostgresCapturePathStore(db_pool)
    assert await store.get(uuid4(), host=None, root=None) is None


@pytest.mark.integration
async def test_upsert_is_idempotent_on_run_id(db_pool: asyncpg.Pool) -> None:
    """A retry (same run_id AND same location) overwrites rather than
    duplicating: `(run_id, host, root)` is the unique key, and
    `ON CONFLICT ... DO UPDATE` is the whole point of the vault being
    mutable, not append-only. Both rows here carry a NULL location, so
    this also exercises the UNIQUE NULLS NOT DISTINCT behaviour the
    re-key migration depends on: under the Postgres default, two NULL
    locations would be distinct and this would insert twice."""
    store = PostgresCapturePathStore(db_pool)
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/first.h5",
        observed_at=_NOW,
        created_at=_NOW,
        host=None,
        root=None,
    )
    await store.upsert(
        run_id=run_id,
        observed_path="/data/second.h5",
        observed_at=_NOW,
        created_at=_NOW,
        host=None,
        root=None,
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM run_capture_path WHERE run_id = $1", run_id
        )
    assert count == 1
    row = await store.get(run_id, host=None, root=None)
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
            host=None,
            root=None,
        )


@pytest.mark.integration
async def test_two_locations_for_one_run_coexist_as_separate_rows(
    db_pool: asyncpg.Pool,
) -> None:
    """The re-key's whole purpose, against real Postgres. Under the old
    `run_id` PRIMARY KEY the archive-tier write below would have
    overwritten the acquisition-tier row, silently invalidating any
    locator already minted against it."""
    store = PostgresCapturePathStore(db_pool)
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/local1/2BM/2026-08-Smith-1015116/scan_005.h5",
        observed_at=_NOW,
        created_at=_NOW,
        host="tomdet",
        root="/local1/2BM",
    )
    await store.upsert(
        run_id=run_id,
        observed_path="/gdata/dm/2BM/2026-08/2026-08-Smith-1015116/data/scan_005.h5",
        observed_at=_NOW,
        created_at=_NOW,
        host="tomdet",
        root="/gdata/dm/2BM",
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM run_capture_path WHERE run_id = $1", run_id
        )
    assert count == 2

    acquisition = await store.get(run_id, host="tomdet", root="/local1/2BM")
    archive = await store.get(run_id, host="tomdet", root="/gdata/dm/2BM")
    assert acquisition is not None
    assert archive is not None
    assert acquisition.observed_path.startswith("/local1/")
    assert archive.observed_path.startswith("/gdata/")


@pytest.mark.integration
async def test_latest_returns_the_most_recently_observed_location(
    db_pool: asyncpg.Pool,
) -> None:
    """`load_run_capture_path`'s contract, proven against the real
    ORDER BY rather than the in-memory adapter's own logic.

    Constructed so ONLY `observed_at` can produce the answer. The
    winning archive row is inserted FIRST and carries the EARLIER
    `created_at`, so an ordering on insert order, on `created_at`, or on
    `updated_at` would all pick the acquisition row instead. The first
    version of this test had the winner leading on every one of those
    axes at once and would have passed with no ORDER BY at all."""
    store = PostgresCapturePathStore(db_pool)
    run_id = uuid4()
    later = _NOW + timedelta(hours=3)
    await store.upsert(
        run_id=run_id,
        observed_path="/gdata/dm/2BM/2026-08/exp/data/scan_005.h5",
        observed_at=later,
        created_at=_NOW,
        host="tomdet",
        root="/gdata/dm/2BM",
    )
    await store.upsert(
        run_id=run_id,
        observed_path="/local1/2BM/exp/scan_005.h5",
        observed_at=_NOW,
        created_at=later,
        host="tomdet",
        root="/local1/2BM",
    )

    row = await store.get_latest(run_id)

    assert row is not None
    assert row.observed_path.startswith("/gdata/")
    assert row.root == "/gdata/dm/2BM"
