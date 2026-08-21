"""Integration: `PostgresDurableDistributionCandidateLookup`'s join against real Postgres.

`run_capture_path`, `proj_run_summary`, `run_experiment_identity`,
`proj_data_dataset_summary`, and `proj_data_distribution_summary` are
populated directly here rather than via the projection pipeline: this
test's whole point is the raw SQL join and anti-join in `_CANDIDATE_SQL`
(a composition-root-only concern spanning the Run and Data BCs, per the
module docstring), not the fold that would normally populate them.

`_insert_run_summary` and `_insert_capture_path` are imported from
`test_capture_scan_ingestor_postgres`, the mirror-image query's own
test module: both queries read the same two Run-BC tables under the
same non-null-location trap, so duplicating those two inserts here
would just be a second place for that trap to go stale.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.api._durable_distribution_sweep import (
    DurableDistributionCandidate,
    PostgresDurableDistributionCandidateLookup,
)
from tests.integration.test_capture_scan_ingestor_postgres import (
    _insert_capture_path,  # pyright: ignore[reportPrivateUsage]
    _insert_run_summary,  # pyright: ignore[reportPrivateUsage]
)

_NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)
_ACQUISITION_ROOT = "/local1/2BM"
_DURABLE_ROOT = "/gdata/dm/2BM"
_CAPTURE_CODE = "2bmb-tomoscan"
_PROPOSAL_NUMBER = "1015116"


async def _insert_dataset(
    pool: asyncpg.Pool, *, producing_run_id: UUID, status: str = "Registered", created_at: datetime
) -> UUID:
    return cast(
        "UUID",
        await pool.fetchval(
            """
            INSERT INTO proj_data_dataset_summary
                (dataset_id, name, uri, producing_run_id, status, created_at)
            VALUES ($1, 'scan.h5', 'file:///x/scan.h5', $2, $3, $4)
            RETURNING dataset_id
            """,
            uuid4(),
            producing_run_id,
            status,
            created_at,
        ),
    )


async def _insert_experiment_identity(
    pool: asyncpg.Pool, *, run_id: UUID, proposal_number: str | None
) -> None:
    await pool.execute(
        """
        INSERT INTO run_experiment_identity (run_id, proposal_number, created_at)
        VALUES ($1, $2, $3)
        """,
        run_id,
        proposal_number,
        _NOW,
    )


async def _insert_distribution(
    pool: asyncpg.Pool, *, dataset_id: UUID, supply_id: UUID, status: str = "Registered"
) -> None:
    """A synthetic Distribution row. Only `dataset_id`, `supply_id`, and
    `status` vary across the tests that use this; the rest are fixed
    filler satisfying the table's NOT NULL / CHECK constraints."""
    await pool.execute(
        """
        INSERT INTO proj_data_distribution_summary
            (distribution_id, dataset_id, supply_id, uri, checksum, byte_size,
             encoding, access_protocol, status, registered_at, registered_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8, $9, $10, $11)
        """,
        uuid4(),
        dataset_id,
        supply_id,
        f"s3://durable/{uuid4()}.h5",
        '{"algorithm": "sha256", "value": "' + "a" * 64 + '"}',
        1024,
        '{"media_type": "application/x-hdf5", "conforms_to": []}',
        "S3",
        status,
        _NOW,
        uuid4(),
    )


async def _seed_ready_candidate(
    pool: asyncpg.Pool,
    *,
    run_id: UUID | None = None,
    observed_path: str = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5",
    proposal_number: str | None = _PROPOSAL_NUMBER,
    dataset_status: str = "Registered",
    dataset_created_at: datetime = _NOW,
    skip_experiment_identity: bool = False,
) -> tuple[UUID, UUID]:
    """Wires up a Run with every row `_CANDIDATE_SQL` wants: a capture
    path, a capture code, an experiment identity, and a Dataset.
    Returns `(run_id, dataset_id)`."""
    run_id = run_id if run_id is not None else uuid4()
    await _insert_run_summary(pool, run_id=run_id, capture_code=_CAPTURE_CODE)
    await _insert_capture_path(
        pool,
        run_id=run_id,
        observed_path=observed_path,
        created_at=_NOW,
        root=_ACQUISITION_ROOT,
    )
    if not skip_experiment_identity:
        await _insert_experiment_identity(pool, run_id=run_id, proposal_number=proposal_number)
    dataset_id = await _insert_dataset(
        pool, producing_run_id=run_id, status=dataset_status, created_at=dataset_created_at
    )
    return run_id, dataset_id


def _lookup(
    pool: asyncpg.Pool,
    *,
    durable_roots: frozenset[str] = frozenset({_DURABLE_ROOT}),
    durable_supply_ids: frozenset[UUID],
) -> PostgresDurableDistributionCandidateLookup:
    return PostgresDurableDistributionCandidateLookup(
        pool, durable_roots=durable_roots, durable_supply_ids=durable_supply_ids
    )


@pytest.mark.integration
async def test_a_dataset_with_vault_row_capture_code_and_proposal_is_returned(
    db_pool: asyncpg.Pool,
) -> None:
    """The happy path: every field on the returned candidate matches
    exactly what was inserted, pinning the SELECT list column-by-column."""
    observed_path = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5"
    run_id, dataset_id = await _seed_ready_candidate(db_pool, observed_path=observed_path)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    candidate = await lookup.next_candidate()

    assert candidate == DurableDistributionCandidate(
        dataset_id=dataset_id,
        run_id=run_id,
        capture_code=_CAPTURE_CODE,
        proposal_number=_PROPOSAL_NUMBER,
        observed_path=observed_path,
        acquisition_root=_ACQUISITION_ROOT,
    )


@pytest.mark.integration
async def test_a_run_with_no_experiment_identity_row_is_not_a_candidate(
    db_pool: asyncpg.Pool,
) -> None:
    """Pins the `JOIN run_experiment_identity` clause: a Run that never
    reached experiment-identity promotion has no row there at all, so
    the inner join drops it before the NULL check even runs."""
    await _seed_ready_candidate(db_pool, skip_experiment_identity=True)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_a_run_with_null_proposal_number_is_not_a_candidate(
    db_pool: asyncpg.Pool,
) -> None:
    """Pins `AND rei.proposal_number IS NOT NULL` specifically: the row
    exists (unlike the join-failure case above) but the substrate never
    reported a proposal, so there is no search key at all."""
    await _seed_ready_candidate(db_pool, proposal_number=None)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_a_dataset_with_a_distribution_at_a_durable_supply_is_not_a_candidate(
    db_pool: asyncpg.Pool,
) -> None:
    """Pins the anti-join's `pdd.supply_id = ANY($3::uuid[])` arm: the
    durable copy is already recorded, so there is nothing left to find."""
    supply_id = uuid4()
    _, dataset_id = await _seed_ready_candidate(db_pool)
    await _insert_distribution(db_pool, dataset_id=dataset_id, supply_id=supply_id)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({supply_id}))
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_a_discarded_distribution_at_a_durable_supply_is_a_candidate_again(
    db_pool: asyncpg.Pool,
) -> None:
    """Pins `AND pdd.status <> 'Discarded'`: a discarded copy is not a
    recorded one, so the Dataset becomes a candidate again."""
    supply_id = uuid4()
    _, dataset_id = await _seed_ready_candidate(db_pool)
    await _insert_distribution(
        db_pool, dataset_id=dataset_id, supply_id=supply_id, status="Discarded"
    )

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({supply_id}))
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.dataset_id == dataset_id


@pytest.mark.integration
async def test_a_distribution_at_a_non_durable_supply_does_not_suppress_the_candidate(
    db_pool: asyncpg.Pool,
) -> None:
    """Without this test, the sibling test pinning the durable-supply
    anti-join would also pass against a query that excludes any Dataset
    with ANY Distribution at all, durable or not, which would be the
    wrong clause: only a durable-supply copy should suppress a
    candidate."""
    durable_supply_id = uuid4()
    other_supply_id = uuid4()
    _, dataset_id = await _seed_ready_candidate(db_pool)
    await _insert_distribution(db_pool, dataset_id=dataset_id, supply_id=other_supply_id)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({durable_supply_id}))
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.dataset_id == dataset_id


@pytest.mark.integration
async def test_a_vault_row_already_at_a_durable_root_is_not_mistaken_for_the_acquisition_row(
    db_pool: asyncpg.Pool,
) -> None:
    """One Run holds two vault rows: one already at the durable root, one
    at the acquisition root. The durable-root row is inserted FIRST, so
    if `NOT (rcp.root = ANY($2::text[]))` were dropped, an unordered join
    across the two rows would surface the durable row's own path first
    and fail this assertion rather than passing by accident."""
    run_id = uuid4()
    acquisition_path = "/local1/2BM/2026-08-Haridy-1015116/scan_005.h5"
    await _insert_run_summary(db_pool, run_id=run_id, capture_code=_CAPTURE_CODE)
    await _insert_capture_path(
        db_pool,
        run_id=run_id,
        observed_path=f"{_DURABLE_ROOT}/2026-08-Haridy-1015116/scan_005.h5",
        created_at=_NOW,
        root=_DURABLE_ROOT,
    )
    await _insert_capture_path(
        db_pool,
        run_id=run_id,
        observed_path=acquisition_path,
        created_at=_NOW,
        root=_ACQUISITION_ROOT,
    )
    await _insert_experiment_identity(db_pool, run_id=run_id, proposal_number=_PROPOSAL_NUMBER)
    dataset_id = await _insert_dataset(db_pool, producing_run_id=run_id, created_at=_NOW)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.dataset_id == dataset_id
    assert candidate.observed_path == acquisition_path
    assert candidate.acquisition_root == _ACQUISITION_ROOT


@pytest.mark.integration
async def test_an_excluded_dataset_id_is_skipped_for_the_next_oldest(
    db_pool: asyncpg.Pool,
) -> None:
    """Pins `NOT (dds.dataset_id = ANY($1::uuid[]))`: excluding one
    Dataset leaves another one reachable."""
    _, older_dataset_id = await _seed_ready_candidate(db_pool, dataset_created_at=_NOW)
    _, newer_dataset_id = await _seed_ready_candidate(
        db_pool, dataset_created_at=_NOW + timedelta(minutes=5)
    )

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    candidate = await lookup.next_candidate(exclude=frozenset({older_dataset_id}))

    assert candidate is not None
    assert candidate.dataset_id == newer_dataset_id


@pytest.mark.integration
async def test_excluding_the_only_candidate_returns_none(db_pool: asyncpg.Pool) -> None:
    _, dataset_id = await _seed_ready_candidate(db_pool)

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    assert await lookup.next_candidate(exclude=frozenset({dataset_id})) is None


@pytest.mark.integration
async def test_a_discarded_dataset_is_not_a_candidate(db_pool: asyncpg.Pool) -> None:
    """Pins `dds.status = 'Registered'`."""
    await _seed_ready_candidate(db_pool, dataset_status="Discarded")

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    assert await lookup.next_candidate() is None


@pytest.mark.integration
async def test_candidates_are_returned_oldest_first(db_pool: asyncpg.Pool) -> None:
    """The winner (older `created_at`) is inserted SECOND, so it loses
    on physical insertion order too: if `ORDER BY dds.created_at ASC`
    were dropped, a plan that falls back to scan/insertion order would
    surface the loser instead, and this assertion would catch it."""
    newer_run_id, older_run_id = uuid4(), uuid4()
    _, newer_dataset_id = await _seed_ready_candidate(
        db_pool,
        run_id=newer_run_id,
        observed_path="/local1/2BM/2026-08-Haridy-1015116/newer.h5",
        dataset_created_at=_NOW,
    )
    _, older_dataset_id = await _seed_ready_candidate(
        db_pool,
        run_id=older_run_id,
        observed_path="/local1/2BM/2026-08-Haridy-1015116/older.h5",
        dataset_created_at=_NOW - timedelta(minutes=5),
    )

    lookup = _lookup(db_pool, durable_supply_ids=frozenset({uuid4()}))
    candidate = await lookup.next_candidate()

    assert candidate is not None
    assert candidate.dataset_id == older_dataset_id
    assert candidate.dataset_id != newer_dataset_id


class _UntouchablePool:
    """Stands in for `asyncpg.Pool` and fails loudly if any query method
    is ever invoked, proving the empty-configuration short circuit never
    reaches Postgres."""

    async def fetchrow(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("next_candidate must not query when unconfigured")


async def test_next_candidate_with_no_durable_roots_or_supply_ids_returns_none_untouched() -> None:
    pool = cast("asyncpg.Pool", _UntouchablePool())

    no_roots = PostgresDurableDistributionCandidateLookup(
        pool, durable_roots=frozenset(), durable_supply_ids=frozenset({uuid4()})
    )
    no_supply_ids = PostgresDurableDistributionCandidateLookup(
        pool, durable_roots=frozenset({_DURABLE_ROOT}), durable_supply_ids=frozenset()
    )

    assert await no_roots.next_candidate() is None
    assert await no_supply_ids.next_candidate() is None
