"""Integration test: `list_permissions` against the seeded bootstrap policy.

End-to-end through PostgresEventStore: the System Bootstrap Policy
seeded by `20260519200000_seed_default_surfaces_and_v2_policy.sql`
permits `SYSTEM_PRINCIPAL_ID` to call `{DefinePolicy, RegisterActor}`
on the nil conduit. `list_permissions` against that policy must return
exactly those two commands, sorted.

`list_permissions` does NOT evaluate the arrival surface (it matches
principal + conduit manually), so the bootstrap policy's HTTP-surface
binding is irrelevant to these assertions; no surface_id is threaded
through the query.

Design lock: `memory/project_permissions_query_design.md`.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.trust._bootstrap import SYSTEM_BOOTSTRAP_POLICY_ID
from cora.trust.features import list_permissions
from cora.trust.features.list_permissions import ListPermissions
from tests.integration._helpers import build_postgres_deps

_NIL_CONDUIT = UUID(int=0)
_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000007aa")


@pytest.mark.integration
async def test_list_permissions_against_bootstrap_policy(db_pool: asyncpg.Pool) -> None:
    """Bootstrap policy permits {DefinePolicy, RegisterActor} for
    SYSTEM_PRINCIPAL_ID on nil conduit. Enumerate returns exactly
    those two commands (sorted alphabetically)."""
    event_store = PostgresEventStore(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, event_store=event_store)
    handler = list_permissions.bind(deps)

    result = await handler(
        ListPermissions(
            policy_id=SYSTEM_BOOTSTRAP_POLICY_ID,
            evaluated_principal_id=SYSTEM_PRINCIPAL_ID,
            evaluated_conduit_id=_NIL_CONDUIT,
        ),
        principal_id=SYSTEM_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == ["DefinePolicy", "RegisterActor"]
    assert result.incomplete is False


@pytest.mark.integration
async def test_list_permissions_against_bootstrap_policy_denies_other_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """A random principal isn't in the bootstrap policy's permitted set
    → enumerate returns empty (no commands accessible to that principal)."""
    event_store = PostgresEventStore(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, event_store=event_store)
    handler = list_permissions.bind(deps)

    rando = UUID("01900000-0000-7000-8000-000000000c01")
    result = await handler(
        ListPermissions(
            policy_id=SYSTEM_BOOTSTRAP_POLICY_ID,
            evaluated_principal_id=rando,
            evaluated_conduit_id=_NIL_CONDUIT,
        ),
        principal_id=SYSTEM_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == []
    assert result.incomplete is False


@pytest.mark.integration
async def test_list_permissions_against_bootstrap_policy_denies_non_nil_conduit(
    db_pool: asyncpg.Pool,
) -> None:
    """Gate-review F6: bootstrap policy's conduit_id is nil
    `UUID(int=0)`. Querying with any other conduit must return empty.
    Pinned at integration tier (handler-level test covers in-memory)
    so PG fold + comparison round-trips correctly."""
    event_store = PostgresEventStore(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, event_store=event_store)
    handler = list_permissions.bind(deps)

    other_conduit = UUID("01900000-0000-7000-8000-00000000cafe")
    result = await handler(
        ListPermissions(
            policy_id=SYSTEM_BOOTSTRAP_POLICY_ID,
            evaluated_principal_id=SYSTEM_PRINCIPAL_ID,
            evaluated_conduit_id=other_conduit,
        ),
        principal_id=SYSTEM_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.permitted_commands == []
    assert result.incomplete is False


@pytest.mark.integration
async def test_list_permissions_returns_none_for_missing_policy(db_pool: asyncpg.Pool) -> None:
    """Nonexistent policy_id → None (route maps to 404)."""
    event_store = PostgresEventStore(db_pool)
    deps = build_postgres_deps(db_pool, now=_NOW, event_store=event_store)
    handler = list_permissions.bind(deps)

    missing = UUID("01900000-0000-7000-8000-deadbeef0002")
    result = await handler(
        ListPermissions(
            policy_id=missing,
            evaluated_principal_id=SYSTEM_PRINCIPAL_ID,
            evaluated_conduit_id=_NIL_CONDUIT,
        ),
        principal_id=SYSTEM_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None
