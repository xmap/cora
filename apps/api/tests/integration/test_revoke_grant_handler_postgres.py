"""End-to-end PG integration test: `revoke_grant` handler.

Single-stream (NOT cross-BC): `revoke_grant` writes only a
`PolicyGrantRevoked` event on the Policy stream, and the folded state
drops the revoked principal from `permitted_principal_ids`. Seeds the
target Policy via the upstream `define_policy` handler so the
define -> revoke walk is exercised end-to-end against real Postgres.

Covers: the happy path (event lands, state shrinks), the silently-
idempotent no-op (revoking an absent principal emits no event), the
not-found rejection, and actor symmetry (a human grant and an agent
grant are removed by the identical path).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy import PolicyNotFoundError, load_policy
from cora.trust.features import define_policy, revoke_grant
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.revoke_grant import RevokeGrant
from tests.integration._helpers import build_postgres_deps

_DEFINED_AT = datetime(2026, 7, 2, 10, 0, 0, tzinfo=UTC)
_REVOKED_AT = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000ad001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000ad002")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-0000000ad003")
_HUMAN = UUID("01900000-0000-7000-8000-0000000ad010")
_AGENT = UUID("01900000-0000-7000-8000-0000000ad011")


async def _seed_policy(
    db_pool: asyncpg.Pool,
    *,
    permitted: frozenset[UUID],
    name: str,
) -> UUID:
    seed_deps = build_postgres_deps(
        db_pool,
        now=_DEFINED_AT,
        ids=[uuid4() for _ in range(4)],
    )
    return await define_policy.bind(seed_deps)(
        DefinePolicy(
            name=name,
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=permitted,
            permitted_commands=frozenset({"HoldRun"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


class _DenyAll:
    async def authorize(self, **_: object) -> Deny:
        return Deny(reason="denied for test")


@pytest.mark.integration
async def test_revoke_grant_removes_principal_and_shrinks_state(
    db_pool: asyncpg.Pool,
) -> None:
    suffix = uuid4().hex[:8]
    policy_id = await _seed_policy(
        db_pool, permitted=frozenset({_HUMAN, _AGENT}), name=f"beam-{suffix}"
    )

    deps = build_postgres_deps(db_pool, now=_REVOKED_AT, ids=[uuid4() for _ in range(2)])
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=_AGENT, reason="agent decommissioned"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    policy = await load_policy(deps.event_store, policy_id)
    assert policy is not None
    assert policy.permitted_principal_ids == frozenset({_HUMAN})

    events, version = await deps.event_store.load("Policy", policy_id)
    assert version == 2  # PolicyDefined + PolicyGrantRevoked
    assert events[-1].event_type == "PolicyGrantRevoked"
    assert events[-1].payload["revoked_principal_id"] == str(_AGENT)
    assert events[-1].payload["revoked_by"] == str(_PRINCIPAL_ID)
    assert events[-1].payload["reason"] == "agent decommissioned"


@pytest.mark.integration
async def test_revoke_grant_absent_principal_is_silent_noop(
    db_pool: asyncpg.Pool,
) -> None:
    """Revoking a principal not in the set emits no event; version unchanged."""
    suffix = uuid4().hex[:8]
    policy_id = await _seed_policy(db_pool, permitted=frozenset({_HUMAN}), name=f"beam-{suffix}")

    deps = build_postgres_deps(db_pool, now=_REVOKED_AT, ids=[uuid4() for _ in range(2)])
    await revoke_grant.bind(deps)(
        RevokeGrant(policy_id=policy_id, principal_id=_AGENT, reason="not present"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _events, version = await deps.event_store.load("Policy", policy_id)
    assert version == 1  # only PolicyDefined; no revoke event appended


@pytest.mark.integration
async def test_revoke_grant_rejects_unknown_policy(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_REVOKED_AT, ids=[uuid4() for _ in range(2)])
    unknown = uuid4()
    with pytest.raises(PolicyNotFoundError) as exc_info:
        await revoke_grant.bind(deps)(
            RevokeGrant(policy_id=unknown, principal_id=_AGENT, reason="whatever"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.policy_id == unknown


@pytest.mark.integration
async def test_revoke_grant_denied_by_authz_raises(
    db_pool: asyncpg.Pool,
) -> None:
    from cora.trust.errors import UnauthorizedError

    suffix = uuid4().hex[:8]
    policy_id = await _seed_policy(db_pool, permitted=frozenset({_AGENT}), name=f"beam-{suffix}")

    deps = build_postgres_deps(
        db_pool,
        now=_REVOKED_AT,
        ids=[uuid4() for _ in range(2)],
        authz=_DenyAll(),  # type: ignore[arg-type]
    )
    with pytest.raises(UnauthorizedError):
        await revoke_grant.bind(deps)(
            RevokeGrant(policy_id=policy_id, principal_id=_AGENT, reason="denied"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Nothing appended: the deny precedes the load/append.
    _events, version = await deps.event_store.load("Policy", policy_id)
    assert version == 1


@pytest.mark.integration
async def test_revoke_grant_human_and_agent_symmetric(
    db_pool: asyncpg.Pool,
) -> None:
    """Actor symmetry (paper I1): the identical handler removes a human
    grant and an agent grant; only the bare UUID differs."""
    suffix = uuid4().hex[:8]
    policy_id = await _seed_policy(
        db_pool, permitted=frozenset({_HUMAN, _AGENT}), name=f"beam-{suffix}"
    )

    deps = build_postgres_deps(db_pool, now=_REVOKED_AT, ids=[uuid4() for _ in range(4)])
    handler = revoke_grant.bind(deps)
    await handler(
        RevokeGrant(policy_id=policy_id, principal_id=_HUMAN, reason="human off-boarded"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        RevokeGrant(policy_id=policy_id, principal_id=_AGENT, reason="agent decommissioned"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    policy = await load_policy(deps.event_store, policy_id)
    assert policy is not None
    assert policy.permitted_principal_ids == frozenset()
