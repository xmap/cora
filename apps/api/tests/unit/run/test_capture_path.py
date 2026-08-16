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
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.run_id == run_id
    assert row.observed_path == "/data/2026-01-Smith-12345/scan_001.h5"
    assert row.observed_at == _at(0)
    assert row.created_at == _at(1)
    assert row.updated_at == _at(1)


@pytest.mark.unit
async def test_get_absent_run_id_returns_none() -> None:
    store = InMemoryCapturePathStore()
    assert await store.get(uuid4()) is None


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
        run_id=run_id, observed_path="/data/first.h5", observed_at=_at(0), created_at=_at(0)
    )
    before_second_upsert = datetime.now(tz=UTC)

    await store.upsert(
        run_id=run_id, observed_path="/data/second.h5", observed_at=_at(5), created_at=_at(5)
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.observed_path == "/data/second.h5"
    assert row.observed_at == _at(5)
    assert row.created_at == _at(0)
    assert row.updated_at >= before_second_upsert


@pytest.mark.unit
async def test_load_run_capture_path_returns_the_real_path_when_present() -> None:
    store = InMemoryCapturePathStore()
    run_id = uuid4()
    await store.upsert(
        run_id=run_id, observed_path="/data/a.h5", observed_at=_at(0), created_at=_at(0)
    )

    assert await load_run_capture_path(store, run_id) == "/data/a.h5"


@pytest.mark.unit
async def test_load_run_capture_path_falls_back_when_absent() -> None:
    """Absence here means 'never observed or rejected by the dual-clock
    guard', not erasure -- there is no erasure slice yet -- but the
    fallback shape is the same as `load_actor_display_name`'s."""
    store = InMemoryCapturePathStore()
    assert await load_run_capture_path(store, uuid4()) == UNOBSERVED_CAPTURE_PATH
