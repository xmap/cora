"""Integration: `PostgresScanIngestCandidateLookup`'s join against real Postgres.

`run_capture_path`, `proj_run_summary`, and `proj_data_dataset_summary`
are populated directly here rather than via the projection pipeline:
this test's whole point is the raw SQL join across those three tables
(two owned by the Run BC, one by the Data BC -- a composition-root-only
concern, per the module docstring), not the fold that would normally
populate them.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._capture_scan_ingestor import PostgresScanIngestCandidateLookup

_NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


async def _insert_run_summary(
    pool: asyncpg.Pool, *, run_id: UUID, capture_code: str | None, status: str = "Completed"
) -> None:
    await pool.execute(
        """
        INSERT INTO proj_run_summary (run_id, name, plan_id, status, created_at, capture_code)
        VALUES ($1, 'Witnessed capture', $2, $3, $4, $5)
        """,
        run_id,
        uuid4(),
        status,
        _NOW,
        capture_code,
    )


async def _insert_capture_path(
    pool: asyncpg.Pool,
    *,
    run_id: UUID,
    observed_path: str,
    created_at: datetime,
    host: str | None = "tomdet",
    root: str | None = "/local1/2BM",
) -> None:
    """Rows default to a RECORDED location, because `_CANDIDATE_SQL`
    excludes rows without one: a locator cannot be minted for a location
    the vault never recorded, so such a row is not a candidate. Pass
    host=None, root=None to build the legacy shape deliberately."""
    await pool.execute(
        """
        INSERT INTO run_capture_path
            (run_id, observed_path, observed_at, created_at, updated_at, host, root)
        VALUES ($1, $2, $3, $4, $4, $5, $6)
        """,
        run_id,
        observed_path,
        created_at,
        created_at,
        host,
        root,
    )


async def _insert_dataset(pool: asyncpg.Pool, *, producing_run_id: UUID) -> None:
    await pool.execute(
        """
        INSERT INTO proj_data_dataset_summary
            (dataset_id, name, uri, producing_run_id, status, created_at)
        VALUES ($1, 'scan.h5', 'file:///x/scan.h5', $2, 'Registered', $3)
        """,
        uuid4(),
        producing_run_id,
        _NOW,
    )


@pytest.mark.integration
async def test_a_run_with_a_path_and_no_dataset_is_a_candidate(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    await _insert_run_summary(db_pool, run_id=run_id, capture_code="2bmb-tomoscan")
    await _insert_capture_path(
        db_pool, run_id=run_id, observed_path="/local1/2BM/scan.h5", created_at=_NOW
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.run_id == run_id
    assert candidate.capture_code == "2bmb-tomoscan"
    assert candidate.observed_path == "/local1/2BM/scan.h5"


@pytest.mark.integration
async def test_a_run_with_a_dataset_already_is_not_a_candidate(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    await _insert_run_summary(db_pool, run_id=run_id, capture_code="2bmb-tomoscan")
    await _insert_capture_path(
        db_pool, run_id=run_id, observed_path="/local1/2BM/scan.h5", created_at=_NOW
    )
    await _insert_dataset(db_pool, producing_run_id=run_id)

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate()

    assert candidate is None


@pytest.mark.integration
async def test_a_run_with_no_capture_path_row_is_never_a_candidate(db_pool: asyncpg.Pool) -> None:
    """A run that never resolved a capture path (the path switch was
    off, or the dual-clock guard rejected it) is not a candidate --
    there is nothing to ingest."""
    run_id = uuid4()
    await _insert_run_summary(db_pool, run_id=run_id, capture_code="2bmb-tomoscan")

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate()

    assert candidate is None


@pytest.mark.integration
async def test_candidates_are_returned_oldest_first(db_pool: asyncpg.Pool) -> None:
    older_run_id, newer_run_id = uuid4(), uuid4()
    await _insert_run_summary(db_pool, run_id=older_run_id, capture_code="2bmb-tomoscan")
    await _insert_run_summary(db_pool, run_id=newer_run_id, capture_code="2bmb-tomoscan")
    await _insert_capture_path(
        db_pool,
        run_id=newer_run_id,
        observed_path="/local1/2BM/newer.h5",
        created_at=_NOW,
    )
    await _insert_capture_path(
        db_pool,
        run_id=older_run_id,
        observed_path="/local1/2BM/older.h5",
        created_at=_NOW - timedelta(minutes=5),
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.run_id == older_run_id


@pytest.mark.integration
async def test_no_candidates_at_all_returns_none(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresScanIngestCandidateLookup(db_pool)
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_an_excluded_run_id_is_skipped_for_the_next_oldest(db_pool: asyncpg.Pool) -> None:
    """The bounded-retry loop's own contract: `exclude` lets `tick()`
    walk past a candidate it already gave up on THIS tick."""
    older_run_id, newer_run_id = uuid4(), uuid4()
    await _insert_run_summary(db_pool, run_id=older_run_id, capture_code="2bmb-tomoscan")
    await _insert_run_summary(db_pool, run_id=newer_run_id, capture_code="2bmb-tomoscan")
    await _insert_capture_path(
        db_pool, run_id=older_run_id, observed_path="/local1/2BM/older.h5", created_at=_NOW
    )
    await _insert_capture_path(
        db_pool,
        run_id=newer_run_id,
        observed_path="/local1/2BM/newer.h5",
        created_at=_NOW + timedelta(minutes=5),
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate(exclude=frozenset({older_run_id}))

    assert candidate is not None
    assert candidate.run_id == newer_run_id


@pytest.mark.integration
async def test_excluding_every_candidate_returns_none(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    await _insert_run_summary(db_pool, run_id=run_id, capture_code="2bmb-tomoscan")
    await _insert_capture_path(
        db_pool, run_id=run_id, observed_path="/local1/2BM/scan.h5", created_at=_NOW
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    assert await lookup.next_candidate(exclude=frozenset({run_id})) is None


@pytest.mark.integration
@pytest.mark.parametrize("status", ["Truncated", "Stopped", "Running", "Held"])
async def test_a_non_terminal_or_truncated_status_is_never_a_candidate(
    db_pool: asyncpg.Pool, status: str
) -> None:
    """Defense-in-depth: `run_capture_path` is written only after a
    successful `RecordWitnessedRunOutcome` today, so a Truncated/Stopped/
    Running/Held run cannot actually hold a capture-path row yet -- but
    the query's own `status IN (...)` filter means a FUTURE change to
    that invariant fails safe (excluded) rather than silently ingesting
    a run that never really finished."""
    run_id = uuid4()
    await _insert_run_summary(db_pool, run_id=run_id, capture_code="2bmb-tomoscan", status=status)
    await _insert_capture_path(
        db_pool, run_id=run_id, observed_path="/local1/2BM/scan.h5", created_at=_NOW
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_an_aborted_run_is_a_candidate(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    await _insert_run_summary(
        db_pool, run_id=run_id, capture_code="2bmb-tomoscan", status="Aborted"
    )
    await _insert_capture_path(
        db_pool, run_id=run_id, observed_path="/local1/2BM/scan.h5", created_at=_NOW
    )

    lookup = PostgresScanIngestCandidateLookup(db_pool)
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.run_id == run_id


@pytest.mark.integration
async def test_a_run_whose_location_was_never_recorded_is_not_a_candidate(
    db_pool: asyncpg.Pool,
) -> None:
    """Rows predating the location columns carry NULL host and root.
    `resolve` derives both from the locator and can never produce NULL,
    so no locator can ever reach such a row. Left as a candidate it
    would be minted for, fail to resolve, and be re-selected as the
    oldest head on every tick forever, logging a SKIP whose reason is
    withheld for PII. Excluding it makes that an explicit non-candidate
    instead of a silent permanent loop."""
    lookup = PostgresScanIngestCandidateLookup(db_pool)
    run_id = uuid4()
    await _insert_run_summary(
        db_pool, run_id=run_id, status="Completed", capture_code="2bmb-tomoscan"
    )
    await _insert_capture_path(
        db_pool,
        run_id=run_id,
        observed_path="/local1/2BM/scan.h5",
        created_at=_NOW,
        host=None,
        root=None,
    )

    assert await lookup.next_candidate() is None

    # Positive control: the same run IS a candidate once a location is
    # recorded, so the exclusion above is about the NULL location and
    # not some unrelated filter in the query.
    await _insert_capture_path(
        db_pool,
        run_id=run_id,
        observed_path="/local1/2BM/scan.h5",
        created_at=_NOW,
    )
    candidate = await lookup.next_candidate()
    assert candidate is not None
    assert candidate.run_id == run_id
    assert candidate.root == "/local1/2BM"
