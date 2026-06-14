"""Integration test: TrustAuthorize against real Postgres.

End-to-end through PostgresEventStore: define a Policy via the real
define_policy handler, then call TrustAuthorize directly. Proves the
fold-on-read load + pure evaluate works against the real adapter.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports import (
    Allow,
    Deny,
)
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-00000abcd001")
_DEFINE_EVENT_ID = UUID("01900000-0000-7000-8000-00000abcd0e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
# Post-3h: handlers pass `UUID(int=0)` (nil) by default; the gating
# policy must use the same conduit_id to match (otherwise evaluate
# denies on conduit mismatch).
_CONDUIT_ID = UUID(int=0)
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


@pytest.mark.integration
async def test_trust_authorize_gates_via_real_postgres_policy(
    db_pool: asyncpg.Pool,
) -> None:
    event_store = PostgresEventStore(db_pool)
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[_POLICY_ID, _DEFINE_EVENT_ID],
        event_store=event_store,
    )

    # Create a real Policy in Postgres.
    await define_policy.bind(deps)(
        DefinePolicy(
            name="Test-policy",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_ALLOWED_PRINCIPAL}),
            permitted_commands=frozenset({"RegisterActor"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Now wire TrustAuthorize against that policy and verify it gates.
    # The policy binds SYSTEM_HTTP_SURFACE_ID; authorize calls present
    # the same arrival surface so the Allow/Deny verdicts turn on the
    # principal (not a surface mismatch).
    authorize = TrustAuthorize(event_store, policy_id=_POLICY_ID)

    allowed = await authorize.authorize(
        _ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0), SYSTEM_HTTP_SURFACE_ID
    )
    assert isinstance(allowed, Allow)

    denied = await authorize.authorize(
        _OTHER_PRINCIPAL, "RegisterActor", UUID(int=0), SYSTEM_HTTP_SURFACE_ID
    )
    assert isinstance(denied, Deny)


@pytest.mark.integration
async def test_trust_authorize_denies_when_policy_missing_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Fail-closed against the real adapter: PostgresEventStore.load
    returns ([], 0) for an empty stream → handler returns None → Deny."""
    event_store = PostgresEventStore(db_pool)
    missing_policy_id = UUID("01900000-0000-7000-8000-deadbeef0001")
    authorize = TrustAuthorize(event_store, policy_id=missing_policy_id)

    result = await authorize.authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "not found" in result.reason.lower()
