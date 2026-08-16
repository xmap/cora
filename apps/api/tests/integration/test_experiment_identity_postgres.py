"""Integration: the `run_experiment_identity` vault against real Postgres.

Mirrors `test_capture_path_postgres.py`'s shape: exercise
`PostgresExperimentIdentityStore` directly against the migrated table,
no handler involved (this store is a plain composition-root dependency,
not wrapped by a command). Also confirms the RLS posture the init
migration declares.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.run.aggregates.run import PostgresExperimentIdentityStore

_NOW = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)


@pytest.mark.integration
async def test_upsert_then_get_roundtrips_through_postgres(db_pool: asyncpg.Pool) -> None:
    store = PostgresExperimentIdentityStore(db_pool)
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_NOW,
        esaf_number="67890",
        esaf_number_observed_at=_NOW,
        esaf_doi_number="10.1234/esaf.67890",
        esaf_doi_number_observed_at=_NOW,
        created_at=_NOW,
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.run_id == run_id
    assert row.proposal_number == "12345"
    assert row.esaf_number == "67890"
    assert row.esaf_doi_number == "10.1234/esaf.67890"


@pytest.mark.integration
async def test_upsert_accepts_a_partial_reading_through_postgres(db_pool: asyncpg.Pool) -> None:
    store = PostgresExperimentIdentityStore(db_pool)
    run_id = uuid4()

    await store.upsert(
        run_id=run_id,
        proposal_number="12345",
        proposal_number_observed_at=_NOW,
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_NOW,
    )

    row = await store.get(run_id)
    assert row is not None
    assert row.proposal_number == "12345"
    assert row.esaf_number is None
    assert row.esaf_doi_number is None


@pytest.mark.integration
async def test_get_absent_run_id_returns_none(db_pool: asyncpg.Pool) -> None:
    store = PostgresExperimentIdentityStore(db_pool)
    assert await store.get(uuid4()) is None


@pytest.mark.integration
async def test_upsert_is_idempotent_on_run_id(db_pool: asyncpg.Pool) -> None:
    """A retry (same run_id, e.g. after a transient failure) overwrites
    rather than duplicating: `run_id` is the PRIMARY KEY, and
    `ON CONFLICT (run_id) DO UPDATE` is the whole point of the vault
    being mutable, not append-only."""
    store = PostgresExperimentIdentityStore(db_pool)
    run_id = uuid4()
    await store.upsert(
        run_id=run_id,
        proposal_number="first",
        proposal_number_observed_at=_NOW,
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_NOW,
    )
    await store.upsert(
        run_id=run_id,
        proposal_number="second",
        proposal_number_observed_at=_NOW,
        esaf_number=None,
        esaf_number_observed_at=None,
        esaf_doi_number=None,
        esaf_doi_number_observed_at=None,
        created_at=_NOW,
    )

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM run_experiment_identity WHERE run_id = $1", run_id
        )
    assert count == 1
    row = await store.get(run_id)
    assert row is not None
    assert row.proposal_number == "second"


@pytest.mark.integration
async def test_table_has_force_row_level_security_enabled(db_pool: asyncpg.Pool) -> None:
    """Defense-in-depth check on the migration itself: FORCE (not just
    ENABLE) means even the table-owner role goes through policy,
    mirroring `run_capture_path`'s identical posture."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = $1",
            "run_experiment_identity",
        )
    assert row is not None
    assert row["relrowsecurity"] is True
    assert row["relforcerowsecurity"] is True


@pytest.mark.integration
async def test_proposal_number_length_constraint_rejects_an_oversized_value(
    db_pool: asyncpg.Pool,
) -> None:
    """Defense-in-depth CHECK bound, independent of the application-layer
    reader (which never fabricates an oversized value on its own but
    should not depend solely on that for a value read off an
    unauthenticated channel)."""
    store = PostgresExperimentIdentityStore(db_pool)
    with pytest.raises(asyncpg.CheckViolationError):
        await store.upsert(
            run_id=uuid4(),
            proposal_number="a" * 201,
            proposal_number_observed_at=_NOW,
            esaf_number=None,
            esaf_number_observed_at=None,
            esaf_doi_number=None,
            esaf_doi_number_observed_at=None,
            created_at=_NOW,
        )


@pytest.mark.integration
async def test_esaf_doi_number_length_constraint_rejects_an_oversized_value(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresExperimentIdentityStore(db_pool)
    with pytest.raises(asyncpg.CheckViolationError):
        await store.upsert(
            run_id=uuid4(),
            proposal_number=None,
            proposal_number_observed_at=None,
            esaf_number=None,
            esaf_number_observed_at=None,
            esaf_doi_number="a" * 501,
            esaf_doi_number_observed_at=_NOW,
            created_at=_NOW,
        )
