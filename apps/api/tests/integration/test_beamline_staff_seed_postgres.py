"""The beamline staff seed ceremony, end to end against real Postgres.

Covers the four claims the task requires proof for: both actors land
under their pinned ids with `kind=human`, a re-run is a true no-op, the
appended event's payload carries no name, and the vault holds the name
that was actually configured for this run, not a placeholder.

Every name used here is invented ("Test Operator A/B"); the real 2-BM
staff names are personal data and never appear in this repository,
including in tests.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.api.beamline_staff_seed import (
    BEAMLINE_STAFF_SLOTS,
    OPERATOR_A_ACTOR_ID,
    OPERATOR_B_ACTOR_ID,
    seed_beamline_staff,
)
from cora.infrastructure.postgres.pool import create_pool
from tests._postgres import normalize_async_url

pytestmark = pytest.mark.integration

SeedDatabase = tuple[asyncpg.Pool, str]

_NAMES: dict[str, str | None] = {
    "2-bm-operator-a": "Test Operator A",
    "2-bm-operator-b": "Test Operator B",
}


@pytest_asyncio.fixture
async def seed_database(
    postgres_container: PostgresContainer,
    template_database: str,
):
    """A per-test database plus its URL, because the ceremony builds its
    own pool from a URL rather than borrowing the fixture's."""
    test_db = f"seed_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool, test_url
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()


async def _run_ceremony(
    url: str, *, dry_run: bool = False, names: dict[str, str | None] | None = None
) -> int:
    return await seed_beamline_staff(
        names_by_slot=_NAMES if names is None else names,
        dry_run=dry_run,
        database_url=url,
    )


async def test_ceremony_seeds_both_actors_with_pinned_ids_and_human_kind(
    seed_database: SeedDatabase,
) -> None:
    pool, url = seed_database

    exit_code = await _run_ceremony(url)
    assert exit_code == 2

    for actor_id in (OPERATOR_A_ACTOR_ID, OPERATOR_B_ACTOR_ID):
        row = await pool.fetchrow(
            "SELECT event_type, payload FROM events WHERE stream_id = $1", actor_id
        )
        assert row is not None
        assert row["event_type"] == "ActorRegisteredV2"
        assert row["payload"]["kind"] == "human"


async def test_ceremony_rerun_changes_nothing(seed_database: SeedDatabase) -> None:
    pool, url = seed_database

    first = await _run_ceremony(url)
    assert first == 2, "first run must report seeded"

    events_after_first = await pool.fetchval("SELECT COUNT(*) FROM events")

    second = await _run_ceremony(url)
    assert second == 0, "second run must report all-exists"

    events_after_second = await pool.fetchval("SELECT COUNT(*) FROM events")
    assert events_after_second == events_after_first, "a re-run must append zero events"


async def test_seeded_event_payload_carries_no_name(seed_database: SeedDatabase) -> None:
    pool, url = seed_database
    assert await _run_ceremony(url) == 2

    for actor_id in (OPERATOR_A_ACTOR_ID, OPERATOR_B_ACTOR_ID):
        payload = await pool.fetchval("SELECT payload FROM events WHERE stream_id = $1", actor_id)
        assert "name" not in payload


async def test_seeded_name_lands_only_in_the_profile_vault(seed_database: SeedDatabase) -> None:
    pool, url = seed_database
    assert await _run_ceremony(url) == 2

    row = await pool.fetchrow(
        "SELECT name FROM actor_profile WHERE actor_id = $1", OPERATOR_A_ACTOR_ID
    )
    assert row is not None
    assert row["name"] == "Test Operator A"

    row_b = await pool.fetchrow(
        "SELECT name FROM actor_profile WHERE actor_id = $1", OPERATOR_B_ACTOR_ID
    )
    assert row_b is not None
    assert row_b["name"] == "Test Operator B"


async def test_dry_run_writes_nothing(seed_database: SeedDatabase) -> None:
    pool, url = seed_database

    exit_code = await _run_ceremony(url, dry_run=True)
    assert exit_code == 2, "dry run against a fresh database reports would-seed"

    stream_ids = [slot.actor_id for slot in BEAMLINE_STAFF_SLOTS]
    event_count = await pool.fetchval(
        "SELECT COUNT(*) FROM events WHERE stream_id = ANY($1::uuid[])", stream_ids
    )
    assert event_count == 0

    profile_count = await pool.fetchval(
        "SELECT COUNT(*) FROM actor_profile WHERE actor_id = ANY($1::uuid[])", stream_ids
    )
    assert profile_count == 0


async def test_missing_name_fails_loudly_and_writes_nothing(seed_database: SeedDatabase) -> None:
    pool, url = seed_database

    exit_code = await _run_ceremony(url, names={"2-bm-operator-a": "Test Operator A"})
    assert exit_code == 1

    stream_ids = [slot.actor_id for slot in BEAMLINE_STAFF_SLOTS]
    event_count = await pool.fetchval(
        "SELECT COUNT(*) FROM events WHERE stream_id = ANY($1::uuid[])", stream_ids
    )
    assert event_count == 0, "a missing name must fail before any write, for either slot"


async def test_blank_name_fails_loudly_and_writes_nothing(seed_database: SeedDatabase) -> None:
    _, url = seed_database

    exit_code = await _run_ceremony(
        url, names={"2-bm-operator-a": "Test Operator A", "2-bm-operator-b": "   "}
    )
    assert exit_code == 1


async def test_mid_ceremony_exception_reports_error_and_exit_one(
    seed_database: SeedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, url = seed_database

    async def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic mid-ceremony failure")

    monkeypatch.setattr("cora.api.beamline_staff_seed.verify_schema_version", explode)

    exit_code = await _run_ceremony(url)
    assert exit_code == 1
