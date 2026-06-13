"""Integration test: evaluate_policy handler against real Postgres.

Round-trips through PostgresEventStore: define a Policy first via
the define_policy handler, then evaluate it via the evaluate_policy
handler. Proves the load_policy fold + evaluate works against the
real adapter (jsonb payload survives → frozenset bridge in evolver
→ pure evaluate produces the right result).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.ports import (
    Allow,
    Deny,
)
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.features import define_policy, evaluate_policy
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.evaluate_policy import EvaluatePolicy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-00000c0c0fc1")
_DEFINE_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0fd1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")
_OTHER_SURFACE = UUID("01900000-0000-7000-8000-00000000face")


@pytest.mark.integration
async def test_evaluate_policy_loads_and_evaluates_through_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_POLICY_ID, _DEFINE_EVENT_ID])

    # Define a Policy through the real handler so it lands in pg as a
    # PolicyDefined event with the expected jsonb shape. Binds the HTTP
    # Surface (define_policy requires a real Surface).
    await define_policy.bind(deps)(
        DefinePolicy(
            name="Beam-team",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_ALLOWED_PRINCIPAL}),
            permitted_commands=frozenset({"RegisterActor"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = evaluate_policy.bind(deps)

    # Hit (allowed): subject matches every facet (incl. surface) → Allow
    allowed = await handler(
        EvaluatePolicy(
            policy_id=_POLICY_ID,
            evaluated_principal_id=_ALLOWED_PRINCIPAL,
            evaluated_command_name="RegisterActor",
            evaluated_conduit_id=_CONDUIT_ID,
            evaluated_surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(allowed, Allow)

    # Hit (denied): wrong principal → Deny with diagnostic reason
    denied = await handler(
        EvaluatePolicy(
            policy_id=_POLICY_ID,
            evaluated_principal_id=_OTHER_PRINCIPAL,
            evaluated_command_name="RegisterActor",
            evaluated_conduit_id=_CONDUIT_ID,
            evaluated_surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(denied, Deny)
    assert "principal" in denied.reason.lower()

    # Hit (denied): mismatched surface → Deny (strict surface matching)
    denied_surface = await handler(
        EvaluatePolicy(
            policy_id=_POLICY_ID,
            evaluated_principal_id=_ALLOWED_PRINCIPAL,
            evaluated_command_name="RegisterActor",
            evaluated_conduit_id=_CONDUIT_ID,
            evaluated_surface_id=_OTHER_SURFACE,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(denied_surface, Deny)
    assert "surface" in denied_surface.reason.lower()


@pytest.mark.integration
async def test_evaluate_policy_returns_none_when_policy_does_not_exist(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin the missing-policy → None contract against the real adapter
    (PostgresEventStore.load returns ([], 0) for an empty stream;
    the handler maps that to None)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[UUID(int=i) for i in range(1, 9)])

    result = await evaluate_policy.bind(deps)(
        EvaluatePolicy(
            policy_id=UUID("01900000-0000-7000-8000-deadbeefdead"),
            evaluated_principal_id=_ALLOWED_PRINCIPAL,
            evaluated_command_name="RegisterActor",
            evaluated_conduit_id=_CONDUIT_ID,
            evaluated_surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None
