"""The schema gate against a real migrated database.

The unit tier drives the comparison with fakes. This tier answers the
question fakes cannot: does the bookkeeping the test fixture writes
actually agree with the constant the application checks, over a database
built the way every other test builds one.

That agreement is load-bearing and easy to lose. The suite applies
migrations by executing the .sql files rather than by running Atlas, so
the revisions table is written by `tests/conftest.py` standing in for
Atlas. If that stand-in and `EXPECTED_SCHEMA_VERSION` ever drift apart,
every app-building test starts failing at boot for a reason that has
nothing to do with what it was testing. This file makes that failure
arrive here, named, instead of scattered across the suite.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.read_only_event_store import (
    EventWritesDisabledError,
    ReadOnlyEventStore,
)
from cora.infrastructure.schema_version import (
    EXPECTED_SCHEMA_VERSION,
    SchemaBehindError,
    read_applied_version,
    verify_schema_version,
)

if TYPE_CHECKING:
    import asyncpg

_STALE = "20260101000000"


async def _rewind_recorded_version(pool: asyncpg.Pool, version: str) -> None:
    """Make the database look like one restored from an older backup.

    Rewriting the bookkeeping rather than un-applying DDL is deliberate:
    the gate reads the recorded version and nothing else, so this
    reproduces exactly the input a restore produces without having to
    reverse 160 migrations to get it.
    """
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM atlas_schema_revisions.atlas_schema_revisions")
        await conn.execute(
            "INSERT INTO atlas_schema_revisions.atlas_schema_revisions (version) VALUES ($1)",
            version,
        )


@pytest.mark.integration
async def test_migrated_database_reports_the_pinned_version(db_pool: asyncpg.Pool) -> None:
    """The fixture's stand-in bookkeeping agrees with the application's pin."""
    assert await read_applied_version(db_pool) == EXPECTED_SCHEMA_VERSION


@pytest.mark.integration
async def test_migrated_database_boots_matched(db_pool: asyncpg.Pool) -> None:
    check = await verify_schema_version(db_pool)
    assert check.posture == "matched"


@pytest.mark.integration
async def test_stale_database_refuses_to_boot(db_pool: asyncpg.Pool) -> None:
    await _rewind_recorded_version(db_pool, _STALE)

    with pytest.raises(SchemaBehindError) as caught:
        await verify_schema_version(db_pool)

    assert caught.value.applied == _STALE
    assert caught.value.expected == EXPECTED_SCHEMA_VERSION


@pytest.mark.integration
async def test_stale_database_with_override_boots_degraded(db_pool: asyncpg.Pool) -> None:
    await _rewind_recorded_version(db_pool, _STALE)

    check = await verify_schema_version(db_pool, allow_mismatch=True)

    assert check.posture == "degraded"
    assert check.applied == _STALE


@pytest.mark.integration
async def test_degraded_boot_refuses_appends_to_the_real_store(db_pool: asyncpg.Pool) -> None:
    """The wiring the override produces, over the real Postgres store.

    Reads still work, which is the whole reason the override exists;
    appends do not, which is the whole reason it is safe.
    """
    await _rewind_recorded_version(db_pool, _STALE)
    check = await verify_schema_version(db_pool, allow_mismatch=True)
    guarded = ReadOnlyEventStore(
        PostgresEventStore(db_pool), applied=check.applied, expected=check.expected
    )

    events, version = await guarded.load("Actor", uuid4())
    assert (events, version) == ([], 0)

    with pytest.raises(EventWritesDisabledError):
        await guarded.append("Actor", uuid4(), 0, [])
