"""Integration tests for the default-surfaces seed migration.

Covers `20260519200000_seed_default_surfaces_and_v2_policy.sql`:
seeds 3 default Surfaces (HTTP, MCP stdio, MCP streamable-http) +
the V2 Bootstrap Policy bound to the HTTP Surface. Wrapped in
BEGIN/COMMIT to avoid partial-fail state where V2 points
at non-existent Surfaces.

Design lock: memory/project_conduit_injection_design.md.
"""

import json
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.trust._bootstrap import (
    SYSTEM_BOOTSTRAP_POLICY_ID,
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)
from cora.trust.aggregates.policy.read import load_policy
from cora.trust.aggregates.surface import SurfaceKind, SurfaceStatus, load_surface

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false


def _decode(value: object) -> dict[str, object]:
    return json.loads(value) if isinstance(value, str) else value  # type: ignore[return-value]


@pytest.mark.integration
async def test_v2_bootstrap_policy_stream_exists(db_pool: asyncpg.Pool) -> None:
    """V2 PolicyDefined event lands at the seeded UUID with the locked
    payload shape (sorted permitted_principal_ids + commands; bound to
    HTTP Surface)."""
    rows = await db_pool.fetch(
        """
        SELECT event_type, payload
        FROM events
        WHERE stream_type = 'Policy' AND stream_id = $1
        ORDER BY version
        """,
        SYSTEM_BOOTSTRAP_POLICY_ID,
    )
    assert len(rows) == 1
    assert rows[0]["event_type"] == "PolicyDefined"
    payload = _decode(rows[0]["payload"])
    assert payload["policy_id"] == str(SYSTEM_BOOTSTRAP_POLICY_ID)
    assert payload["name"] == "System Bootstrap Policy V2"
    assert payload["conduit_id"] == "00000000-0000-0000-0000-000000000000"
    assert payload["surface_id"] == str(SYSTEM_HTTP_SURFACE_ID)
    assert payload["permitted_commands"] == ["DefinePolicy", "RegisterActor"]
    assert payload["permitted_principal_ids"] == ["00000000-0000-0000-0000-000000000000"]


@pytest.mark.integration
async def test_three_default_surfaces_seeded(db_pool: asyncpg.Pool) -> None:
    """All 3 Surface streams (HTTP, MCP stdio, MCP streamable-http)
    land at their seeded UUIDs."""
    expected = {
        SYSTEM_HTTP_SURFACE_ID: ("System HTTP", "http"),
        SYSTEM_MCP_STDIO_SURFACE_ID: ("System MCP stdio", "mcp_stdio"),
        SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID: (
            "System MCP streamable-http",
            "mcp_streamable_http",
        ),
    }
    rows = await db_pool.fetch(
        """
        SELECT stream_id, payload
        FROM events
        WHERE stream_type = 'Surface' AND stream_id = ANY($1::uuid[])
        ORDER BY stream_id
        """,
        list(expected.keys()),
    )
    assert len(rows) == 3
    for row in rows:
        payload = _decode(row["payload"])
        expected_name, expected_kind = expected[row["stream_id"]]
        assert payload["name"] == expected_name
        assert payload["kind"] == expected_kind


@pytest.mark.integration
async def test_v2_policy_folds_with_surface_binding(db_pool: asyncpg.Pool) -> None:
    """`load_policy` returns a Policy folded with `surface_id =
    SYSTEM_HTTP_SURFACE_ID` (the post-Iter-B Policy state shape)."""
    event_store = PostgresEventStore(db_pool)
    policy = await load_policy(event_store, SYSTEM_BOOTSTRAP_POLICY_ID)
    assert policy is not None
    assert policy.id == SYSTEM_BOOTSTRAP_POLICY_ID
    assert policy.surface_id == SYSTEM_HTTP_SURFACE_ID
    assert policy.conduit_id == UUID(int=0)
    assert policy.permitted_commands == frozenset({"DefinePolicy", "RegisterActor"})


@pytest.mark.integration
async def test_http_surface_folds_correctly(db_pool: asyncpg.Pool) -> None:
    event_store = PostgresEventStore(db_pool)
    surface = await load_surface(event_store, SYSTEM_HTTP_SURFACE_ID)
    assert surface is not None
    assert surface.id == SYSTEM_HTTP_SURFACE_ID
    assert surface.kind == SurfaceKind.HTTP
    assert surface.status == SurfaceStatus.DEFINED


@pytest.mark.integration
async def test_seed_migration_is_idempotent(db_pool: asyncpg.Pool) -> None:
    """Re-applying the migration is a silent no-op (the 4 INSERTs
    use ON CONFLICT DO NOTHING)."""
    from pathlib import Path

    migration_sql = (
        Path(__file__).resolve().parents[4]  # noqa: ASYNC240 — tiny SQL file, sync read OK in test
        / "infra"
        / "atlas"
        / "migrations"
        / "20260519200000_seed_default_surfaces_and_v2_policy.sql"
    ).read_text()

    surface_count_before = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Surface'"
    )
    v2_count_before = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Policy' AND stream_id = $1",
        SYSTEM_BOOTSTRAP_POLICY_ID,
    )

    async with db_pool.acquire() as conn:
        await conn.execute(migration_sql)

    surface_count_after = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Surface'"
    )
    v2_count_after = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'Policy' AND stream_id = $1",
        SYSTEM_BOOTSTRAP_POLICY_ID,
    )

    assert surface_count_before == surface_count_after
    assert v2_count_before == v2_count_after == 1
