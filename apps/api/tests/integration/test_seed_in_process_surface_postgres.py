"""Integration tests for the in-process-Surface seed migration.

Covers `20260831150000_seed_in_process_surface.sql`: seeds the
`SYSTEM_IN_PROCESS_SURFACE_ID` Surface (kind=in_process), the door CORA's
own in-process work (agent tick loops, capture readers, one-time operator
entrypoints) now uses instead of falling through to `NIL_SENTINEL_ID`.
"""

import json
from pathlib import Path

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.routing import SYSTEM_IN_PROCESS_SURFACE_ID
from cora.trust.aggregates.surface import SurfaceKind, SurfaceStatus, load_surface

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false


def _decode(value: object) -> dict[str, object]:
    return json.loads(value) if isinstance(value, str) else value  # type: ignore[return-value]


@pytest.mark.integration
async def test_in_process_surface_stream_exists(db_pool: asyncpg.Pool) -> None:
    """A single `SurfaceDefined` event lands at the seeded UUID with the
    locked payload shape (kind=in_process)."""
    rows = await db_pool.fetch(
        """
        SELECT event_type, payload
        FROM events
        WHERE stream_type = 'Surface' AND stream_id = $1
        ORDER BY version
        """,
        SYSTEM_IN_PROCESS_SURFACE_ID,
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "SurfaceDefined"
    payload = _decode(rows[0]["payload"])
    assert payload["surface_id"] == str(SYSTEM_IN_PROCESS_SURFACE_ID)
    assert payload["name"] == "System In-process"
    assert payload["kind"] == "in_process"


@pytest.mark.integration
async def test_in_process_surface_folds_to_in_process_kind(db_pool: asyncpg.Pool) -> None:
    """`load_surface` returns a Surface folded with `kind =
    SurfaceKind.IN_PROCESS`, status DEFINED (v1 only ever emits DEFINED)."""
    event_store = PostgresEventStore(db_pool)
    surface = await load_surface(event_store, SYSTEM_IN_PROCESS_SURFACE_ID)
    assert surface is not None
    assert surface.id == SYSTEM_IN_PROCESS_SURFACE_ID
    assert surface.kind == SurfaceKind.IN_PROCESS
    assert surface.status == SurfaceStatus.DEFINED


@pytest.mark.integration
async def test_seed_migration_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Re-applying the migration is a silent no-op (the INSERT uses
    ON CONFLICT DO NOTHING)."""
    migration_sql = (
        Path(__file__).resolve().parents[4]  # noqa: ASYNC240 (tiny SQL file, sync read OK in test)
        / "infra"
        / "atlas"
        / "migrations"
        / "20260831150000_seed_in_process_surface.sql"
    ).read_text()

    count_before = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Surface' AND stream_id = $1",
        SYSTEM_IN_PROCESS_SURFACE_ID,
    )

    async with db_pool.acquire() as conn:
        await conn.execute(migration_sql)

    count_after = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Surface' AND stream_id = $1",
        SYSTEM_IN_PROCESS_SURFACE_ID,
    )

    assert count_before == count_after == 1
