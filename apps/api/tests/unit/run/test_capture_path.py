"""Unit tests for the `run_capture_path` PII vault's InMemory adapter
and the `load_run_capture_path` display-fallback helper (slice 13).

Mirrors `test_feed_heartbeats.py`'s shape: exercise the store contract
directly, no recorder or observer involved.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.aggregates.run import (
    UNOBSERVED_CAPTURE_PATH,
    InMemoryCapturePathStore,
    load_run_capture_path,
)

_T0 = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


@pytest.mark.unit
async def test_upsert_then_get_roundtrips() -> None:
    store = InMemoryCapturePathStore()
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        observed_path="/data/2026-01-Smith-12345/scan_001.h5",
        observed_at=_at(0),
        created_at=_at(1),
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.run_id == run_id
    assert row.observed_path == "/data/2026-01-Smith-12345/scan_001.h5"
    assert row.observed_at == _at(0)
    assert row.created_at == _at(1)
    assert row.updated_at == _at(1)


@pytest.mark.unit
async def test_get_absent_run_id_returns_none() -> None:
    store = InMemoryCapturePathStore()
    assert await store.get(uuid4(), host=None, root=None) is None


@pytest.mark.unit
async def test_upsert_overwrites_and_preserves_created_at() -> None:
    """A second upsert for the same run_id (a rewrite, e.g. a retry)
    updates the path and observed_at but keeps the ORIGINAL created_at,
    mirroring the Postgres adapter's `ON CONFLICT DO UPDATE` (which
    never touches the column). `updated_at` on the UPDATE branch is the
    STORE's own clock (`datetime.now(tz=UTC)`), mirroring
    `InMemoryProfileStore`'s identical Postgres-semantics-preserved
    convention (the real adapter's `ON CONFLICT DO UPDATE` sets
    `updated_at = now()`, the DB's clock, never the caller-supplied
    `created_at` parameter) -- never the fixed `_at(5)` passed in.
    """
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/first.h5",
        observed_at=_at(0),
        created_at=_at(0),
        host=None,
        root=None,
    )
    before_second_upsert = datetime.now(tz=UTC)

    await store.upsert(
        run_id=run_id,
        observed_path="/data/second.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.observed_path == "/data/second.h5"
    assert row.observed_at == _at(5)
    assert row.created_at == _at(0)
    assert row.updated_at >= before_second_upsert


@pytest.mark.unit
async def test_upsert_older_observed_at_leaves_row_unchanged() -> None:
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/first.h5",
        observed_at=_at(10),
        created_at=_at(10),
        host=None,
        root=None,
    )

    await store.upsert(
        run_id=run_id,
        observed_path="/data/stale.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.observed_path == "/data/first.h5"
    assert row.observed_at == _at(10)
    assert row.updated_at == _at(10)


@pytest.mark.unit
async def test_upsert_newer_observed_at_still_updates() -> None:
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/first.h5",
        observed_at=_at(0),
        created_at=_at(0),
        host=None,
        root=None,
    )
    before_second_upsert = datetime.now(tz=UTC)

    await store.upsert(
        run_id=run_id,
        observed_path="/data/second.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.observed_path == "/data/second.h5"
    assert row.observed_at == _at(5)
    assert row.updated_at >= before_second_upsert


@pytest.mark.unit
async def test_upsert_equal_observed_at_still_updates() -> None:
    """The guard is `>=`, not `>`: a genuine retry of the SAME
    observation (identical `observed_at`) that carries a corrected path
    must still land, e.g. a recorder retrying after a transient write
    failure with no new reading in between."""
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/first.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host=None,
        root=None,
    )
    before_second_upsert = datetime.now(tz=UTC)

    await store.upsert(
        run_id=run_id,
        observed_path="/data/corrected.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host=None,
        root=None,
    )

    row = await store.get(run_id, host=None, root=None)
    assert row is not None
    assert row.observed_path == "/data/corrected.h5"
    assert row.observed_at == _at(5)
    assert row.updated_at >= before_second_upsert


@pytest.mark.unit
async def test_get_latest_ignores_stale_replay_against_the_newer_location() -> None:
    """The bug this guard fixes, not just the row-level symptom: with
    two locations for one run, a stale EPICS replay against the
    location that is ALREADY the newest must not corrupt its
    `observed_at` down below the OTHER location's, or `get_latest`
    would start returning the wrong location entirely, not merely the
    wrong path for the right location."""
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/gdata/dm/2BM/exp/scan_005.h5",
        observed_at=_at(5),
        created_at=_at(5),
        host="tomdet",
        root="/gdata/dm/2BM",
    )
    await store.upsert(
        run_id=run_id,
        observed_path="/local1/2BM/exp/scan_005.h5",
        observed_at=_at(10),
        created_at=_at(10),
        host="tomdet",
        root="/local1/2BM",
    )

    await store.upsert(
        run_id=run_id,
        observed_path="/local1/2BM/exp/STALE_scan_005.h5",
        observed_at=_at(1),
        created_at=_at(1),
        host="tomdet",
        root="/local1/2BM",
    )

    row = await store.get_latest(run_id)
    assert row is not None
    assert row.observed_path == "/local1/2BM/exp/scan_005.h5"
    assert row.root == "/local1/2BM"


@pytest.mark.unit
async def test_load_run_capture_path_returns_the_real_path_when_present() -> None:
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/data/a.h5",
        observed_at=_at(0),
        created_at=_at(0),
        host=None,
        root=None,
    )

    assert await load_run_capture_path(store, run_id) == "/data/a.h5"


@pytest.mark.unit
async def test_load_run_capture_path_falls_back_when_absent() -> None:
    """Absence here means 'never observed or rejected by the dual-clock
    guard', not erasure -- there is no erasure slice yet -- but the
    fallback shape is the same as `load_actor_display_name`'s."""
    store = InMemoryCapturePathStore()
    assert await load_run_capture_path(store, uuid4()) == UNOBSERVED_CAPTURE_PATH


@pytest.mark.unit
async def test_get_latest_returns_the_most_recently_observed_row_across_locations() -> None:
    """Deliberately the SAME scenario as the Postgres integration test
    of the same name, so the two adapters are checked against one
    scenario rather than each against itself. The winner is inserted
    first and carries the earlier `created_at`, so only `observed_at`
    ordering can produce it."""
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        observed_path="/gdata/dm/2BM/2026-08/exp/data/scan_005.h5",
        observed_at=_at(5),
        created_at=_at(0),
        host="tomdet",
        root="/gdata/dm/2BM",
    )
    await store.upsert(
        run_id=run_id,
        observed_path="/local1/2BM/exp/scan_005.h5",
        observed_at=_at(0),
        created_at=_at(5),
        host="tomdet",
        root="/local1/2BM",
    )

    row = await store.get_latest(run_id)

    assert row is not None
    assert row.observed_path.startswith("/gdata/")


@pytest.mark.unit
async def test_get_latest_never_returns_another_runs_row() -> None:
    store = InMemoryCapturePathStore()
    mine, theirs = uuid4(), uuid4()
    await store.upsert(
        run_id=theirs,
        observed_path="/data/theirs.h5",
        observed_at=_at(9),
        created_at=_at(9),
        host="tomdet",
        root="/data",
    )

    assert await store.get_latest(mine) is None


@pytest.mark.unit
async def test_get_latest_breaks_a_full_tie_deterministically() -> None:
    """Two rows identical on `observed_at` AND `updated_at` is not an
    exotic shape: it is what two upserts sharing one clock read produce.
    `_LATEST_SQL` breaks the tie on `capture_path_id DESC` and this
    adapter must agree, or a test that is deterministic here is flaky in
    CI."""
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    for root in ("/a", "/b"):
        await store.upsert(
            run_id=run_id,
            observed_path=f"{root}/scan.h5",
            observed_at=_at(0),
            created_at=_at(0),
            host="tomdet",
            root=root,
        )
    rows = [
        await store.get(run_id, host="tomdet", root="/a"),
        await store.get(run_id, host="tomdet", root="/b"),
    ]
    winner = await store.get_latest(run_id)

    assert winner is not None
    assert winner.capture_path_id == max(r.capture_path_id for r in rows if r is not None)
