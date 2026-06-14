"""End-to-end: `list_policies` handler against real Postgres
projection table.

Pins the INSERT round-trip through the full projection path
(PolicyDefined -> proj_trust_policy_summary INSERT) including the
conduit_id column surfacing as a filter target.

  - Sanity: PolicyDefined inserts a row with conduit_id surfaced.
  - conduit_id filter narrows results to one of two policies.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust._projections import register_trust_projections
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.define_policy import bind as bind_define_policy
from cora.trust.features.list_policies import ListPolicies
from cora.trust.features.list_policies import bind as bind_list
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    """Drain Trust projections."""
    registry = ProjectionRegistry()
    register_trust_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_policy_defined_inserts_with_conduit_ref(
    db_pool: asyncpg.Pool,
) -> None:
    policy_id = uuid4()
    conduit_id = uuid4()
    deps = _build_deps(db_pool, [policy_id, uuid4()])
    await bind_define_policy(deps)(
        DefinePolicy(
            name="OperatorAccess",
            conduit_id=conduit_id,
            permitted_principal_ids=frozenset({_PRINCIPAL_ID}),
            permitted_commands=frozenset({"StartRun"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT policy_id, name, conduit_id, created_at "
            "FROM proj_trust_policy_summary WHERE policy_id = $1",
            policy_id,
        )
    assert row is not None
    assert row["name"] == "OperatorAccess"
    assert row["conduit_id"] == conduit_id
    assert row["created_at"] == _NOW


@pytest.mark.integration
async def test_conduit_id_filter_narrows_results(db_pool: asyncpg.Pool) -> None:
    conduit_a = uuid4()
    conduit_b = uuid4()

    policy_a = uuid4()
    deps_a = _build_deps(db_pool, [policy_a, uuid4()])
    await bind_define_policy(deps_a)(
        DefinePolicy(
            name="for-conduit-a",
            conduit_id=conduit_a,
            permitted_principal_ids=frozenset(),
            permitted_commands=frozenset(),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    policy_b = uuid4()
    deps_b = _build_deps(db_pool, [policy_b, uuid4()])
    await bind_define_policy(deps_b)(
        DefinePolicy(
            name="for-conduit-b",
            conduit_id=conduit_b,
            permitted_principal_ids=frozenset(),
            permitted_commands=frozenset(),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps_a)
    page = await handler(
        ListPolicies(conduit_id=conduit_a, limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].policy_id == policy_a
    assert page.items[0].conduit_id == conduit_a


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListPolicies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None
