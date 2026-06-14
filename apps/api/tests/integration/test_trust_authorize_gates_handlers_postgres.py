"""Integration test: TrustAuthorize gates real handler calls end-to-end.

First verification pass of the post-handler-gate Trust integration.
Existing `test_trust_authorize_postgres.py` proves the adapter loads
and evaluates against real Postgres when called *directly*. This file
proves the missing piece: that the adapter, wired via `wire_trust`
into a `TrustHandlers` bundle (with the full `with_tracing` /
`with_idempotency` composition), correctly gates handler calls —
permitted principals succeed, non-permitted principals raise
`UnauthorizedError`, and a misconfigured policy_id fails closed.

Test setup uses TWO `Kernel` against a shared Postgres pool:

  1. Bootstrap deps (`AllowAllAuthorize`) defines the policy that
     gates everything. The chicken-and-egg from TrustAuthorize's
     docstring — a later pass pins the documented bootstrap workflow
     more thoroughly.
  2. Production deps (`TrustAuthorize` against the bootstrap policy)
     wire the BC handlers under real authz. Tests call those handlers
     and assert on the gating outcome.

Why `define_zone` as the gated handler: it's a create-style command
with idempotency wrap, so success exercises the full
`with_tracing(with_idempotency(bind))` chain — the same composition
every BC's create-style handlers use. Cross-BC scenarios (Subject
handlers gated by Trust policy) land in the cross-BC sibling file.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust import UnauthorizedError, wire_trust
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from cora.trust.features.define_zone import DefineZone
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
# Post-3h: handlers pass nil conduit_id; gating policy matches.
_CONDUIT_ID = UUID(int=0)
_PERMITTED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")
_BOOTSTRAP_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _bootstrap_deps(
    db_pool: asyncpg.Pool,
    *,
    ids: list[UUID],
) -> Kernel:
    """Build Kernel with AllowAllAuthorize for the policy-define step."""
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


def _gated_deps(
    db_pool: asyncpg.Pool,
    *,
    policy_id: UUID,
    ids: list[UUID],
) -> Kernel:
    """Build Kernel with TrustAuthorize gating against `policy_id`."""
    event_store = PostgresEventStore(db_pool)
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=ids,
        authz=TrustAuthorize(event_store, policy_id=policy_id),
        event_store=event_store,
    )


@pytest.mark.integration
async def test_trust_authorize_allows_handler_call_for_permitted_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: TrustAuthorize-wired wire_trust handler call succeeds
    when the principal is in the policy's permitted set. Pinned because
    every prior integration test wires AllowAllAuthorize, leaving the
    "TrustAuthorize gates real handlers" path untested at the BC-level
    composition (with_tracing + with_idempotency + bind)."""
    policy_id = UUID("01900000-0000-7000-8000-0000000b1001")
    policy_event_id = UUID("01900000-0000-7000-8000-0000000b10e1")
    zone_id = UUID("01900000-0000-7000-8000-0000000b1002")
    zone_event_id = UUID("01900000-0000-7000-8000-0000000b10e2")

    # 1) Define a policy permitting only `_PERMITTED_PRINCIPAL` to DefineZone.
    bootstrap = _bootstrap_deps(db_pool, ids=[policy_id, policy_event_id])
    await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="GateA-PermitDefineZone",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
            permitted_commands=frozenset({"DefineZone"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )

    # 2) Build production deps gated by that policy and wire BC handlers.
    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[zone_id, zone_event_id])
    handlers = wire_trust(gated)

    # 3) Permitted principal calls define_zone via the production chain.
    #    Present the same arrival surface the policy binds so the gate
    #    Allows on principal + command (not a surface mismatch).
    result = await handlers.define_zone(
        DefineZone(name="GateA-AllowedZone"),
        principal_id=_PERMITTED_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert result == zone_id


@pytest.mark.integration
async def test_trust_authorize_denies_handler_call_for_other_principal(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: TrustAuthorize-wired wire_trust handler call raises
    `UnauthorizedError` when the principal is not in the policy's
    permitted set. The error reason carries the diagnostic from
    `evaluate()`."""
    policy_id = UUID("01900000-0000-7000-8000-0000000b2001")
    policy_event_id = UUID("01900000-0000-7000-8000-0000000b20e1")
    # Reserve zone ids even though the call should fail before any are consumed.
    spare_id_1 = UUID("01900000-0000-7000-8000-0000000b2002")
    spare_id_2 = UUID("01900000-0000-7000-8000-0000000b20e2")

    bootstrap = _bootstrap_deps(db_pool, ids=[policy_id, policy_event_id])
    await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="GateA-DenyOthers",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
            permitted_commands=frozenset({"DefineZone"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )

    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[spare_id_1, spare_id_2])
    handlers = wire_trust(gated)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handlers.define_zone(
            DefineZone(name="GateA-DeniedZone"),
            principal_id=_OTHER_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on principal, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
    assert str(_OTHER_PRINCIPAL) in exc_info.value.reason


@pytest.mark.integration
async def test_trust_authorize_denies_handler_call_when_command_not_permitted(
    db_pool: asyncpg.Pool,
) -> None:
    """The principal IS in the permitted set, but the policy does not
    permit DefineZone (only RegisterActor). Pinned so a future
    relaxation that ignores `permitted_commands` is caught — both
    dimensions of the policy must gate."""
    policy_id = UUID("01900000-0000-7000-8000-0000000b3001")
    policy_event_id = UUID("01900000-0000-7000-8000-0000000b30e1")
    spare_id_1 = UUID("01900000-0000-7000-8000-0000000b3002")
    spare_id_2 = UUID("01900000-0000-7000-8000-0000000b30e2")

    bootstrap = _bootstrap_deps(db_pool, ids=[policy_id, policy_event_id])
    await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="GateA-WrongCommand",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
            # Note: DefineZone is NOT in this set.
            permitted_commands=frozenset({"RegisterActor"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )

    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[spare_id_1, spare_id_2])
    handlers = wire_trust(gated)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handlers.define_zone(
            DefineZone(name="GateA-WrongCommandZone"),
            principal_id=_PERMITTED_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on command, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
    assert "DefineZone" in exc_info.value.reason


@pytest.mark.integration
async def test_trust_authorize_fails_closed_when_configured_policy_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """Misconfigured deployment: `trust_policy_id` points at a
    policy that doesn't exist in the event store. TrustAuthorize
    returns Deny (fail-closed; documented in its docstring), and the
    handler chain surfaces it as `UnauthorizedError`. Pinned because
    silently allowing the call would be a security incident."""
    missing_policy_id = UUID("01900000-0000-7000-8000-deadbeef0a01")
    spare_id_1 = UUID("01900000-0000-7000-8000-deadbeef0a02")
    spare_id_2 = UUID("01900000-0000-7000-8000-deadbeef0a03")

    gated = _gated_deps(db_pool, policy_id=missing_policy_id, ids=[spare_id_1, spare_id_2])
    handlers = wire_trust(gated)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handlers.define_zone(
            DefineZone(name="GateA-MissingPolicyZone"),
            principal_id=_PERMITTED_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
        )
    assert "not found" in exc_info.value.reason.lower()


@pytest.mark.integration
async def test_trust_authorize_denies_when_policy_conduit_does_not_match_handler_conduit(
    db_pool: asyncpg.Pool,
) -> None:
    """3h behavior: a Policy bound to one `conduit_id` denies calls
    that arrive with a different `conduit_id`. End-to-end pin (Phase
    A is wire_trust composition; the unit-level mismatch test in
    `test_trust_authorize.py` covers the adapter directly). Pinned
    because conduit-routing is the WHOLE point of 3h — without this,
    the typed conduit_id parameter would be cosmetic.

    Setup: seed a policy bound to a NON-nil conduit_id, then call
    define_zone via the wire chain. The handler passes nil
    (`UUID(int=0)`, today's default), which evaluate rejects on
    conduit-mismatch.
    """
    policy_id = UUID("01900000-0000-7000-8000-0000000b4001")
    policy_event_id = UUID("01900000-0000-7000-8000-0000000b40e1")
    spare_id_1 = UUID("01900000-0000-7000-8000-0000000b4002")
    spare_id_2 = UUID("01900000-0000-7000-8000-0000000b40e2")
    other_conduit_id = UUID("01900000-0000-7000-8000-0000000b40c0")

    # Note: this test SEEDs with a non-nil conduit_id (overriding the
    # module-level _CONDUIT_ID = nil) to exercise the mismatch path.
    bootstrap = _bootstrap_deps(db_pool, ids=[policy_id, policy_event_id])
    await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="GateA-OtherConduit",
            conduit_id=other_conduit_id,
            permitted_principal_ids=frozenset({_PERMITTED_PRINCIPAL}),
            permitted_commands=frozenset({"DefineZone"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )

    gated = _gated_deps(db_pool, policy_id=policy_id, ids=[spare_id_1, spare_id_2])
    handlers = wire_trust(gated)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handlers.define_zone(
            DefineZone(name="GateA-MismatchZone"),
            # Permitted principal AND command — only conduit mismatches.
            principal_id=_PERMITTED_PRINCIPAL,
            correlation_id=_CORRELATION_ID,
        )
    assert "conduit" in exc_info.value.reason.lower()
