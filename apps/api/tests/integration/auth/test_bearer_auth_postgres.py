"""Integration tests for the bearer-auth path against real Postgres.

End-to-end through the production `IdentityProviderRegistry` +
`JwtTokenVerifier` + `StaticSubjectMapper` composition over an
in-process JWKS endpoint (`pytest-httpserver`). The middleware path
exists as a thin shell around `verifier.verify(token,
expected_audience=surface_id)`; these tests drive the same call
sequence and then feed the resolved principal into the real Access
+ Trust handler chains backed by `PostgresEventStore` +
`PostgresIdempotencyStore`.

Three pins:

  1. **JWKS happy path**: a JWT signed by the test keypair verifies
     against a `JwtTokenVerifier` configured with the matching JWKS
     URL. The resolved `principal_id` is the binding-mapped Actor id
     (not SYSTEM, not the raw `sub`), and the downstream
     `register_actor` write lands on the event store with that
     same `principal_id`.

  2. **TrustAuthorize end-to-end**: a Policy in PostgresEventStore
     permits one bearer-mapped principal and denies another. The
     permitted JWT runs through to a successful event append; the
     denied JWT raises Access's `UnauthorizedError`. Pins the
     full JWKS -> verifier -> resolved-principal -> TrustAuthorize ->
     decider chain against the real adapter.

  3. **Idempotency cross-principal**: two distinct JWTs (two `sub`
     claims, two principal_ids) sharing the same `Idempotency-Key`
     and command body do NOT collide. The idempotency PK is
     `(principal_id, key, surface_id)` per
     `apps/api/src/cora/infrastructure/adapters/postgres_idempotency_store.py`,
     so a shared key under different principals lives in different
     rows and both writes succeed with distinct actor ids. Rejection
     (`IdempotencyConflictError` -> 422) only fires within a single
     principal on a body mismatch (already pinned at the contract
     tier).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest
from pytest_httpserver import HTTPServer

from cora.access import UnauthorizedError as AccessUnauthorizedError
from cora.access import wire_access
from cora.access.aggregates.actor import ActorKind
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.adapters.postgres_idempotency_store import PostgresIdempotencyStore
from cora.infrastructure.auth.build_idp_registry import build_idp_registry
from cora.infrastructure.auth.config import (
    IdentityProviderConfig,
    IdpSubjectBinding,
    build_static_subject_mapper,
)
from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.authorize import TrustAuthorize
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests.integration._helpers import build_postgres_deps
from tests.unit.auth._helpers import (
    TEST_AUD_HTTP,
    TEST_ISSUER,
    make_keypair_with_jwks,
    sign_jwt,
)

_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000bea01")
_CONDUIT_ID = UUID(int=0)

_PRINCIPAL_HAPPY = UUID("01900000-0000-7000-8000-0000000bea11")
_PRINCIPAL_PERMITTED = UUID("01900000-0000-7000-8000-0000000bea21")
_PRINCIPAL_DENIED = UUID("01900000-0000-7000-8000-0000000bea22")
_PRINCIPAL_IDEMP_A = UUID("01900000-0000-7000-8000-0000000bea31")
_PRINCIPAL_IDEMP_B = UUID("01900000-0000-7000-8000-0000000bea32")
_BOOTSTRAP_PRINCIPAL = UUID("01900000-0000-7000-8000-0000000bea99")


def _idps(jwks_url: str, bindings: dict[str, UUID]) -> list[IdentityProviderConfig]:
    """Build a single-IdP config list with the given subject -> Actor map."""
    return [
        IdentityProviderConfig(
            issuer=TEST_ISSUER,
            jwks_url=jwks_url,
            audiences={SYSTEM_HTTP_SURFACE_ID: TEST_AUD_HTTP},
            allowed_algorithms=["RS256"],
            principal_kind="human",
            allow_insecure_jwks_url=True,
            subject_bindings=[
                IdpSubjectBinding(subject=sub, actor_id=actor_id)
                for sub, actor_id in bindings.items()
            ],
        )
    ]


def _build_registry(jwks_url: str, bindings: dict[str, UUID]):
    """Wire the production `IdentityProviderRegistry` against the test JWKS.

    Mirrors the production `build_kernel` composition: same
    `build_static_subject_mapper` + `build_idp_registry` factory pair,
    just with test-local `IdentityProviderConfig` instances instead
    of Settings-loaded ones.
    """
    configs = _idps(jwks_url, bindings)
    mapper = build_static_subject_mapper(configs)
    registry = build_idp_registry(configs, subject_mapper=mapper)
    assert registry is not None
    return registry


# ---------- Test 1: JWKS happy path end-to-end ----------


@pytest.mark.integration
async def test_bearer_jwks_happy_path_postgres(
    db_pool: asyncpg.Pool, httpserver: HTTPServer
) -> None:
    private_key, kid, jwks_url = make_keypair_with_jwks(httpserver, "/jwks-happy")
    registry = _build_registry(jwks_url, {"user-happy": _PRINCIPAL_HAPPY})

    token = sign_jwt(private_key, kid, sub="user-happy")
    principal = await registry.verify(token, expected_audience=SYSTEM_HTTP_SURFACE_ID)
    assert principal.principal_id == _PRINCIPAL_HAPPY
    assert principal.issuer == TEST_ISSUER
    assert principal.subject == "user-happy"

    actor_id = uuid4()
    register_event_id = uuid4()
    event_store = PostgresEventStore(db_pool)
    idempotency_store = PostgresIdempotencyStore(db_pool)
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[actor_id, register_event_id],
        event_store=event_store,
        idempotency_store=idempotency_store,
    )
    handlers = wire_access(deps)

    returned_actor_id = await handlers.register_actor(
        RegisterActor(name="HappyPathActor", kind=ActorKind.HUMAN),
        principal_id=principal.principal_id,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_actor_id == actor_id

    events, _ = await event_store.load("Actor", actor_id)
    assert len(events) == 1
    assert events[0].event_type == "ActorRegisteredV2"
    assert events[0].principal_id == _PRINCIPAL_HAPPY


# ---------- Test 2: TrustAuthorize gates a bearer-mapped principal ----------


@pytest.mark.integration
async def test_bearer_trust_authorize_end_to_end_postgres(
    db_pool: asyncpg.Pool, httpserver: HTTPServer
) -> None:
    private_key, kid, jwks_url = make_keypair_with_jwks(httpserver, "/jwks-trust")
    registry = _build_registry(
        jwks_url,
        {
            "user-permitted": _PRINCIPAL_PERMITTED,
            "user-denied": _PRINCIPAL_DENIED,
        },
    )

    policy_id = uuid4()
    policy_event_id = uuid4()
    event_store = PostgresEventStore(db_pool)

    bootstrap = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[policy_id, policy_event_id],
        event_store=event_store,
    )
    await define_policy.bind(bootstrap)(
        DefinePolicy(
            name="BearerGate-PermitRegisterActor",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_PRINCIPAL_PERMITTED}),
            permitted_commands=frozenset({"RegisterActor"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_BOOTSTRAP_PRINCIPAL,
        correlation_id=_CORRELATION_ID,
    )

    permitted_token = sign_jwt(private_key, kid, sub="user-permitted")
    permitted_principal = await registry.verify(
        permitted_token, expected_audience=SYSTEM_HTTP_SURFACE_ID
    )
    assert permitted_principal.principal_id == _PRINCIPAL_PERMITTED

    permitted_actor_id = uuid4()
    permitted_event_id = uuid4()
    gated_permitted = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[permitted_actor_id, permitted_event_id],
        event_store=event_store,
        authz=TrustAuthorize(event_store, policy_id=policy_id),
    )
    handlers_permitted = wire_access(gated_permitted)

    returned_id = await handlers_permitted.register_actor(
        RegisterActor(name="TrustGate-Permitted", kind=ActorKind.HUMAN),
        principal_id=permitted_principal.principal_id,
        correlation_id=_CORRELATION_ID,
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
    assert returned_id == permitted_actor_id

    events, _ = await event_store.load("Actor", permitted_actor_id)
    assert len(events) == 1
    assert events[0].principal_id == _PRINCIPAL_PERMITTED

    denied_token = sign_jwt(private_key, kid, sub="user-denied")
    denied_principal = await registry.verify(denied_token, expected_audience=SYSTEM_HTTP_SURFACE_ID)
    assert denied_principal.principal_id == _PRINCIPAL_DENIED

    denied_actor_id = uuid4()
    denied_event_id = uuid4()
    gated_denied = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[denied_actor_id, denied_event_id],
        event_store=event_store,
        authz=TrustAuthorize(event_store, policy_id=policy_id),
    )
    handlers_denied = wire_access(gated_denied)

    with pytest.raises(AccessUnauthorizedError) as exc_info:
        await handlers_denied.register_actor(
            RegisterActor(name="TrustGate-Denied", kind=ActorKind.HUMAN),
            principal_id=denied_principal.principal_id,
            correlation_id=_CORRELATION_ID,
            # Matching surface so the deny is on principal, not surface.
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        )
    assert str(_PRINCIPAL_DENIED) in exc_info.value.reason

    denied_events, _ = await event_store.load("Actor", denied_actor_id)
    assert denied_events == []


# ---------- Test 3: idempotency key is scoped per-principal ----------


@pytest.mark.integration
async def test_bearer_idempotency_cross_principal_postgres(
    db_pool: asyncpg.Pool, httpserver: HTTPServer
) -> None:
    """Same `Idempotency-Key` + same body under two different bearer-
    resolved principals creates two distinct rows. The idempotency PK
    `(principal_id, key, surface_id)` lives at
    apps/api/src/cora/infrastructure/adapters/postgres_idempotency_store.py
    so per-principal namespacing is structural; cross-principal
    collisions are NOT possible by construction. The 422
    `IdempotencyConflictError` rejection only fires within a single
    principal on a body mismatch (pinned in
    tests/contract/test_define_conduit_idempotency.py)."""
    private_key, kid, jwks_url = make_keypair_with_jwks(httpserver, "/jwks-idemp")
    registry = _build_registry(
        jwks_url,
        {
            "user-idemp-a": _PRINCIPAL_IDEMP_A,
            "user-idemp-b": _PRINCIPAL_IDEMP_B,
        },
    )

    token_a = sign_jwt(private_key, kid, sub="user-idemp-a")
    token_b = sign_jwt(private_key, kid, sub="user-idemp-b")
    principal_a = await registry.verify(token_a, expected_audience=SYSTEM_HTTP_SURFACE_ID)
    principal_b = await registry.verify(token_b, expected_audience=SYSTEM_HTTP_SURFACE_ID)
    assert principal_a.principal_id == _PRINCIPAL_IDEMP_A
    assert principal_b.principal_id == _PRINCIPAL_IDEMP_B
    assert principal_a.principal_id != principal_b.principal_id

    actor_id_a = uuid4()
    event_id_a = uuid4()
    event_store = PostgresEventStore(db_pool)
    idempotency_store = PostgresIdempotencyStore(db_pool)

    deps_a = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[actor_id_a, event_id_a],
        event_store=event_store,
        idempotency_store=idempotency_store,
    )
    handlers_a = wire_access(deps_a)
    returned_a = await handlers_a.register_actor(
        RegisterActor(name="SharedKeyActor", kind=ActorKind.HUMAN),
        principal_id=principal_a.principal_id,
        correlation_id=_CORRELATION_ID,
        idempotency_key="ik-cross-principal",
    )
    assert returned_a == actor_id_a

    actor_id_b = uuid4()
    event_id_b = uuid4()
    deps_b = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[actor_id_b, event_id_b],
        event_store=event_store,
        idempotency_store=idempotency_store,
    )
    handlers_b = wire_access(deps_b)
    returned_b = await handlers_b.register_actor(
        RegisterActor(name="SharedKeyActor", kind=ActorKind.HUMAN),
        principal_id=principal_b.principal_id,
        correlation_id=_CORRELATION_ID,
        idempotency_key="ik-cross-principal",
    )
    assert returned_b == actor_id_b
    assert returned_a != returned_b

    events_a, _ = await event_store.load("Actor", actor_id_a)
    events_b, _ = await event_store.load("Actor", actor_id_b)
    assert len(events_a) == 1
    assert len(events_b) == 1
    assert events_a[0].principal_id == _PRINCIPAL_IDEMP_A
    assert events_b[0].principal_id == _PRINCIPAL_IDEMP_B
