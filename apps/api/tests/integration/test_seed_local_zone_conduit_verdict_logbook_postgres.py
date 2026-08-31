"""Integration tests for the local Zone/Conduit/verdict-logbook seed migration.

Covers `20260831140000_seed_local_zone_conduit_verdict_logbook.sql`:
seeds SYSTEM_LOCAL_ZONE_ID, SYSTEM_LOCAL_CONDUIT_ID, and an open verdict
logbook on the Conduit's own stream. Inert until an operator sets
`Settings.trust_conduit_id`; see watch item 6 of
memory/project_authorization_envelope_design.md.
"""

import json
from pathlib import Path

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.routing import SYSTEM_LOCAL_CONDUIT_ID, SYSTEM_LOCAL_ZONE_ID
from cora.trust.aggregates.conduit import LOGBOOK_KIND_VERDICT, load_conduit
from cora.trust.aggregates.zone import load_zone

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false


def _decode(value: object) -> dict[str, object]:
    return json.loads(value) if isinstance(value, str) else value  # type: ignore[return-value]


@pytest.mark.integration
async def test_local_zone_stream_exists(db_pool: asyncpg.Pool) -> None:
    rows = await db_pool.fetch(
        "SELECT event_type, payload FROM events WHERE stream_type = 'Zone' AND stream_id = $1"
        " ORDER BY version",
        SYSTEM_LOCAL_ZONE_ID,
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "ZoneDefined"
    payload = _decode(rows[0]["payload"])
    assert payload["zone_id"] == str(SYSTEM_LOCAL_ZONE_ID)
    assert payload["name"] == "System Local Zone"


@pytest.mark.integration
async def test_local_conduit_stream_has_genesis_and_logbook_opened(
    db_pool: asyncpg.Pool,
) -> None:
    rows = await db_pool.fetch(
        "SELECT version, event_type, payload FROM events"
        " WHERE stream_type = 'Conduit' AND stream_id = $1 ORDER BY version",
        SYSTEM_LOCAL_CONDUIT_ID,
    )
    assert len(rows) == 2

    defined = _decode(rows[0]["payload"])
    assert rows[0]["event_type"] == "ConduitDefined"
    assert rows[0]["version"] == 1
    assert defined["conduit_id"] == str(SYSTEM_LOCAL_CONDUIT_ID)
    assert defined["name"] == "System Local Conduit"
    assert defined["source_zone_id"] == str(SYSTEM_LOCAL_ZONE_ID)
    assert defined["target_zone_id"] == str(SYSTEM_LOCAL_ZONE_ID)

    opened = _decode(rows[1]["payload"])
    assert rows[1]["event_type"] == "ConduitLogbookOpened"
    assert rows[1]["version"] == 2
    assert opened["conduit_id"] == str(SYSTEM_LOCAL_CONDUIT_ID)
    assert opened["kind"] == "verdict"
    schema = opened["schema"]
    assert isinstance(schema, dict)
    assert set(schema["fields"].keys()) == {"actor_id", "command_name", "decision", "reason"}


@pytest.mark.integration
async def test_local_conduit_folds_with_an_open_verdict_logbook(db_pool: asyncpg.Pool) -> None:
    """The property downstream code actually depends on: `load_conduit`
    returns a Conduit whose `logbooks[LOGBOOK_KIND_VERDICT]` is set, the
    exact condition `verify_local_conduit_seed_present` and
    `TrustAuthorize._emit_verdict` both check."""
    event_store = PostgresEventStore(db_pool)
    conduit = await load_conduit(event_store, SYSTEM_LOCAL_CONDUIT_ID)
    assert conduit is not None
    assert conduit.id == SYSTEM_LOCAL_CONDUIT_ID
    assert conduit.source_zone_id == SYSTEM_LOCAL_ZONE_ID
    assert conduit.target_zone_id == SYSTEM_LOCAL_ZONE_ID
    assert LOGBOOK_KIND_VERDICT in conduit.logbooks


@pytest.mark.integration
async def test_local_zone_folds_correctly(db_pool: asyncpg.Pool) -> None:
    event_store = PostgresEventStore(db_pool)
    zone = await load_zone(event_store, SYSTEM_LOCAL_ZONE_ID)
    assert zone is not None
    assert zone.id == SYSTEM_LOCAL_ZONE_ID


@pytest.mark.integration
async def test_seed_migration_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Re-applying the migration is a silent no-op (every INSERT uses
    ON CONFLICT DO NOTHING)."""
    migration_sql = (
        Path(__file__).resolve().parents[4]  # noqa: ASYNC240 (tiny SQL file, sync read OK in test)
        / "infra"
        / "atlas"
        / "migrations"
        / "20260831140000_seed_local_zone_conduit_verdict_logbook.sql"
    ).read_text()

    zone_count_before = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Zone' AND stream_id = $1",
        SYSTEM_LOCAL_ZONE_ID,
    )
    conduit_count_before = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Conduit' AND stream_id = $1",
        SYSTEM_LOCAL_CONDUIT_ID,
    )

    async with db_pool.acquire() as conn:
        await conn.execute(migration_sql)

    zone_count_after = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Zone' AND stream_id = $1",
        SYSTEM_LOCAL_ZONE_ID,
    )
    conduit_count_after = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Conduit' AND stream_id = $1",
        SYSTEM_LOCAL_CONDUIT_ID,
    )

    assert zone_count_before == zone_count_after == 1
    assert conduit_count_before == conduit_count_after == 2
