"""Kernel-construction orchestration.

`build_kernel` builds the process-wide `Kernel` from `Settings`,
called once from the FastAPI lifespan. The authorize-port factory
is INJECTED via the `authorize_factory` callable so this module
has zero BC imports (Phase-8d hardening: the prior version lazy-
imported `cora.trust` for `_build_authorize`, which tach correctly
flagged as a layer violation even though Python tolerated it).

Composition root (`cora.api.main`) injects
`cora.trust.build_authorize.build_authorize`; tests inject any
`Authorize` factory they want (typically
`lambda *a, **kw: AllowAllAuthorize()`).

Adapter selection is driven by `Settings.app_env`:
  - `test` -> in-memory adapters (no Postgres needed; used by
    contract tests of API surface that don't care about
    persistence semantics)
  - anything else -> Postgres-backed adapters over an asyncpg pool

`build_kernel` returns the kernel and a `teardown` callable so the
lifespan can release pool resources without `Kernel` having to
expose its private state.

## Single-Kernel-construction-site invariant

`Kernel(...)` is constructed in exactly two places: `make_postgres_kernel`
and `make_inmemory_kernel` below. Production's `build_kernel` calls
the appropriate primitive with `SystemClock` / `UUIDv7Generator` /
env-loaded `Settings`; tests call the same primitives via thin
wrappers in `tests/unit/_helpers.py` and `tests/integration/_helpers.py`
that supply `FakeClock` / `FixedIdGenerator` / test `Settings`.

The architecture fitness function
`tests/architecture/test_kernel_construction_single_site.py` enforces
this invariant: any direct `Kernel(...)` call outside this module
fails the build. Adding a required `Kernel` field then needs to land
in exactly two function bodies (the two primitives) instead of every
test file individually.
"""

from typing import Protocol

import asyncpg

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.adapters.in_memory_credential_lookup import InMemoryCredentialLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from cora.infrastructure.adapters.in_memory_profile_store import InMemoryProfileStore
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.adapters.postgres_idempotency_store import PostgresIdempotencyStore
from cora.infrastructure.adapters.postgres_profile_store import PostgresProfileStore
from cora.infrastructure.adapters.signing_registry import SigningRegistry
from cora.infrastructure.auth import build_idp_registry, build_static_subject_mapper
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel, Teardown
from cora.infrastructure.logging import configure_logging
from cora.infrastructure.ports import (
    LLM,
    AllSatisfiedSupplyLookup,
    AlwaysCoveredClearanceLookup,
    AlwaysQuietCautionLookup,
    Authorize,
    CautionLookup,
    ClearanceLookup,
    Clock,
    CredentialLookup,
    EventStore,
    IdempotencyStore,
    IdGenerator,
    LogbookMirror,
    ProfileStore,
    SupplyLookup,
    SystemClock,
    TokenVerifier,
    UUIDv7Generator,
)
from cora.infrastructure.postgres.pool import create_pool


class AuthorizeFactory(Protocol):
    """Builds the production Authorize port for the Kernel.

    Injected by the composition root so this module stays BC-free.
    Production wires `cora.trust.build_authorize.build_authorize`;
    tests inject lambda-shaped factories.
    """

    def __call__(
        self,
        settings: Settings,
        event_store: EventStore,
        *,
        pool: asyncpg.Pool | None,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> Authorize: ...


def _build_default_canonicalization_registry() -> CanonicalizationRegistry:
    """Return a CanonicalizationRegistry with the v1 default adapter registered.

    The v1 adapter MUST be registered in every CORA deployment per
    project_canonicalization_port_design.md; the default version is
    set to "cora/v1" so write-side call sites resolve via the
    deployment-wide default. Future v2+ adapters register alongside
    via configuration without dislodging v1.
    """
    registry = CanonicalizationRegistry()
    registry.register("cora/v1", DefaultCanonicalizationAdapter())
    registry.set_default("cora/v1")
    return registry


def make_postgres_kernel(
    pool: asyncpg.Pool,
    *,
    settings: Settings,
    clock: Clock,
    id_generator: IdGenerator,
    authz: Authorize,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    clearance_lookup: ClearanceLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    supply_lookup: SupplyLookup | None = None,
    credential_lookup: CredentialLookup | None = None,
    profile_store: ProfileStore | None = None,
    llm: LLM | None = None,
    logbook_mirror: LogbookMirror | None = None,
    token_verifier: TokenVerifier | None = None,
) -> Kernel:
    """Postgres-backed Kernel primitive.

    Single construction site for `Kernel(...)` with a Postgres pool.
    Production's `build_kernel` postgres branch calls this with
    `SystemClock` + `UUIDv7Generator` + env-loaded `Settings` + the
    `authorize` instance built around `event_store`. Integration tests
    call it via the `tests.integration._helpers.build_postgres_deps`
    wrapper, which supplies `FakeClock` + `FixedIdGenerator` + test
    `Settings`.

    `event_store` / `idempotency_store` default to fresh
    `PostgresEventStore(pool)` / `PostgresIdempotencyStore(pool)` for
    test convenience. Production passes the prebuilt instances so
    they're shared with the authorize_factory (chicken-and-egg:
    `authorize` needs `event_store` before the Kernel is constructed).

    `clearance_lookup` defaults to `AlwaysCoveredClearanceLookup` (the
    test-bypass stub) so existing Run integration tests don't have to
    seed real clearances. Production's `build_kernel` injects the real
    `PostgresClearanceLookup` via the `clearance_lookup_factory`
    argument; gate-specific tests override here explicitly.

    `caution_lookup` defaults to `AlwaysQuietCautionLookup` (returns
    `[]`) so existing Run integration tests don't have to seed
    cautions. Production's `build_kernel` injects the real
    `PostgresCautionLookup` via the `caution_lookup_factory` argument;
    snapshot-specific tests override here explicitly. NON-BLOCKING by
    construction (see `cora.infrastructure.ports.caution_lookup`).

    `supply_lookup` defaults to `AllSatisfiedSupplyLookup` (synthetic
    Available per requested kind) so existing Run / Procedure tests
    don't have to seed real Supplies. Production's `build_kernel`
    injects the real `PostgresSupplyLookup` via the
    `supply_lookup_factory` argument; gate-specific tests override
    here explicitly. See [[project_supply_preflight_gate_design]].

    `credential_lookup` defaults to a fresh `InMemoryCredentialLookup`
    (empty record map). Seal handler / decider tests seed credentials
    explicitly via the adapter's `register(...)` helper; non-Seal
    tests never touch it, so an empty default is safe. Production's
    `build_kernel` injects the real `PostgresCredentialLookup` via the
    `credential_lookup_factory` argument.

    `llm` defaults to `None` because most BCs and tests don't need
    an LLM; only Agent BC subscribers consume it. Production's
    `build_kernel` injects `AnthropicLLM` when
    `Settings.anthropic_api_key` is set; subscriber-level tests
    inject `FakeLLM` explicitly.

    `logbook_mirror` defaults to `None`; no production implementor
    exists yet. Subscribers short-circuit on `None`.

    `token_verifier` defaults to `None`; production `build_kernel`
    constructs it from `settings.identity_providers` when that list
    is non-empty. Integration tests override only when exercising
    the bearer-auth path.
    """
    return Kernel(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authz=authz,
        event_store=event_store if event_store is not None else PostgresEventStore(pool),
        idempotency_store=(
            idempotency_store if idempotency_store is not None else PostgresIdempotencyStore(pool)
        ),
        clearance_lookup=(
            clearance_lookup if clearance_lookup is not None else AlwaysCoveredClearanceLookup()
        ),
        caution_lookup=(
            caution_lookup if caution_lookup is not None else AlwaysQuietCautionLookup()
        ),
        supply_lookup=(supply_lookup if supply_lookup is not None else AllSatisfiedSupplyLookup()),
        credential_lookup=(
            credential_lookup if credential_lookup is not None else InMemoryCredentialLookup()
        ),
        profile_store=(profile_store if profile_store is not None else PostgresProfileStore(pool)),
        canonicalization_registry=_build_default_canonicalization_registry(),
        signing_registry=SigningRegistry(),
        pool=pool,
        llm=llm,
        logbook_mirror=logbook_mirror,
        token_verifier=token_verifier,
    )


def make_inmemory_kernel(
    *,
    settings: Settings,
    clock: Clock,
    id_generator: IdGenerator,
    authz: Authorize,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    clearance_lookup: ClearanceLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    supply_lookup: SupplyLookup | None = None,
    credential_lookup: CredentialLookup | None = None,
    profile_store: ProfileStore | None = None,
    llm: LLM | None = None,
    logbook_mirror: LogbookMirror | None = None,
    token_verifier: TokenVerifier | None = None,
    pool: object | None = None,
) -> Kernel:
    """In-memory Kernel primitive.

    Single construction site for `Kernel(...)` with no Postgres pool.
    Production's `build_kernel` `app_env=test` branch calls this for
    contract tests of the API surface. Unit tests call it via the
    `tests.unit._helpers.build_deps` wrapper.

    `pool` exists as an optional override exclusively for the
    idempotency-pruner tests, which need a non-None sentinel to
    exercise the "pool present" branch of the lifespan task without
    standing up a real Postgres connection. Production callers (and
    every other test) leave it as the default `None`.

    `clearance_lookup` defaults to `AlwaysCoveredClearanceLookup` (the
    test-bypass stub) because the in-memory kernel has no projection
    worker running and no `proj_safety_clearance_summary` table. Gate-
    specific tests can override with a custom adapter built around an
    InMemory event store walk.

    `caution_lookup` defaults to `AlwaysQuietCautionLookup` (returns
    `[]`) for the same reason: no projection worker, no
    `proj_caution_summary` table. Snapshot-specific tests can override
    with a custom adapter or a fake that returns seeded references.

    `supply_lookup` defaults to `AllSatisfiedSupplyLookup` for the same
    reason: no projection worker, no `proj_supply_summary` table to
    read from. Gate-specific tests can override with
    `NoSuppliesRegisteredLookup` (missing-kind path) or a custom fake.

    `credential_lookup` defaults to a fresh `InMemoryCredentialLookup`
    for the same reason: no projection worker, no
    `proj_federation_credential_summary` table to read from. Seal
    handler / decider tests seed credentials via the adapter's
    `register(...)` helper; tests that don't touch the seal slices
    leave the dict empty (the default).

    `llm` defaults to `None`; the in-memory kernel is for unit /
    contract tests that don't exercise LLM subscribers. Subscriber
    tests that DO exercise the LLM path inject `FakeLLM`
    explicitly.

    `logbook_mirror` defaults to `None`; no production implementor
    yet. Subscriber tests inject a `FakeLogbookMirror` (when they
    care) or leave `None`.

    `token_verifier` defaults to `None`; only bearer-auth contract
    tests inject a verifier (a programmable test stub or a real
    `IdentityProviderRegistry` against a fake JWKS server).
    Production wiring lives in `build_kernel`.
    """
    return Kernel(
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authz=authz,
        event_store=event_store if event_store is not None else InMemoryEventStore(),
        idempotency_store=(
            idempotency_store if idempotency_store is not None else InMemoryIdempotencyStore()
        ),
        clearance_lookup=(
            clearance_lookup if clearance_lookup is not None else AlwaysCoveredClearanceLookup()
        ),
        caution_lookup=(
            caution_lookup if caution_lookup is not None else AlwaysQuietCautionLookup()
        ),
        supply_lookup=(supply_lookup if supply_lookup is not None else AllSatisfiedSupplyLookup()),
        credential_lookup=(
            credential_lookup if credential_lookup is not None else InMemoryCredentialLookup()
        ),
        profile_store=profile_store if profile_store is not None else InMemoryProfileStore(),
        canonicalization_registry=_build_default_canonicalization_registry(),
        signing_registry=SigningRegistry(),
        # pool is intentionally typed `object | None` on this factory's
        # signature (per the docstring: idempotency-pruner tests pass a
        # non-None sentinel without standing up real asyncpg). Kernel.pool
        # is `asyncpg.Pool | None`; the ignore acknowledges the
        # widening-then-narrowing seam.
        pool=pool,  # type: ignore[arg-type]
        llm=llm,
        logbook_mirror=logbook_mirror,
        token_verifier=token_verifier,
    )


class ClearanceLookupFactory(Protocol):
    """Builds the production ClearanceLookup port for the Kernel.

    Safety BC's `cora.safety.adapters.PostgresClearanceLookup` is
    the production factory; `cora.api.main` binds it. Same
    factory-injection shape as `AuthorizeFactory` so
    `cora.infrastructure.deps` doesn't import from any BC (tach
    module rule: `cora.infrastructure depends_on = []`).

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysCoveredClearanceLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> ClearanceLookup: ...


class CautionLookupFactory(Protocol):
    """Builds the production CautionLookup port for the Kernel.

    Caution BC's `cora.caution.adapters.PostgresCautionLookup` is
    the production factory; `cora.api.main` binds it. Same
    factory-injection shape as `AuthorizeFactory` /
    `ClearanceLookupFactory` so `cora.infrastructure.deps` doesn't
    import from any BC (tach module rule:
    `cora.infrastructure depends_on = []`).

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysQuietCautionLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> CautionLookup: ...


class SupplyLookupFactory(Protocol):
    """Builds the production SupplyLookup port for the Kernel.

    Supply BC's `cora.supply.adapters.PostgresSupplyLookup` is the
    production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AllSatisfiedSupplyLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> SupplyLookup: ...


class CredentialLookupFactory(Protocol):
    """Builds the production CredentialLookup port for the Kernel.

    Federation BC's `cora.federation.adapters.PostgresCredentialLookup`
    is the production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC (tach module
    rule: `cora.infrastructure depends_on = []`).

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryCredentialLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> CredentialLookup: ...


class LLMFactory(Protocol):
    """Builds the production LLM for the Kernel.

    Agent BC's `cora.agent.adapters.AnthropicLLM` is the
    only production factory today; `cora.api.main` binds it when
    `Settings.anthropic_api_key` is set. Same factory-injection
    shape as `AuthorizeFactory` / `ClearanceLookupFactory` /
    `CautionLookupFactory` so `cora.infrastructure.deps` doesn't
    import from any BC (tach module rule:
    `cora.infrastructure depends_on = []`).

    `settings` is passed (rather than just an API key) so the
    factory can read provider-specific options (timeouts,
    max_retries, base URL overrides) without growing the factory
    surface every time. The factory's `__call__` returns `None`
    when settings indicate no LLM should be wired (eg.
    `anthropic_api_key` unset) so the Kernel ends up with
    `llm=None` and Agent subscribers fail-fast at registration.
    """

    def __call__(
        self,
        settings: Settings,
    ) -> LLM | None: ...


async def build_kernel(
    *,
    authorize_factory: AuthorizeFactory,
    clearance_lookup_factory: ClearanceLookupFactory | None = None,
    caution_lookup_factory: CautionLookupFactory | None = None,
    supply_lookup_factory: SupplyLookupFactory | None = None,
    credential_lookup_factory: CredentialLookupFactory | None = None,
    llm_factory: LLMFactory | None = None,
    settings: Settings | None = None,
) -> tuple[Kernel, Teardown]:
    """Construct the kernel. Called once from the FastAPI lifespan.

    `llm_factory`: when provided, called with `Settings` and the
    result wired into `kernel.llm`. When `None`, `kernel.llm` is
    `None` and Agent BC subscribers that depend on it fail-fast at
    registration. Test mode (`app_env=test`) does NOT call the
    factory; tests inject `FakeLLM` directly via
    `make_inmemory_kernel(..., llm=...)`.

    `settings` is an optional injection point for tests that need
    to override env-var-loaded config (for example edge-auth contract
    tests overriding `identity_providers`). Production callers pass
    nothing; Settings reads from env / .env as usual.

    `token_verifier` is constructed from
    `settings.identity_providers` via `build_idp_registry`. Empty
    list -> `None` -> middleware falls through to the legacy
    `X-Principal-Id` path. Non-empty -> a `TokenVerifier` that
    middleware uses to verify every inbound `Authorization: Bearer`
    header. Constructed in BOTH the test and Postgres branches so
    contract tests for the bearer path can inject `identity_providers`
    via Settings and exercise verification end-to-end (no Postgres
    needed for the verifier itself).
    """
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from env
    configure_logging(settings.log_level)
    clock = SystemClock()
    id_generator = UUIDv7Generator()
    token_verifier: TokenVerifier | None = build_idp_registry(
        settings.identity_providers,
        subject_mapper=build_static_subject_mapper(settings.identity_providers),
    )

    if settings.app_env == "test":
        event_store: EventStore = InMemoryEventStore()
        idempotency_store: IdempotencyStore = InMemoryIdempotencyStore()
        authz = authorize_factory(
            settings,
            event_store,
            pool=None,
            clock=clock,
            id_generator=id_generator,
        )
        kernel = make_inmemory_kernel(
            settings=settings,
            clock=clock,
            id_generator=id_generator,
            authz=authz,
            event_store=event_store,
            idempotency_store=idempotency_store,
            token_verifier=token_verifier,
        )
        return kernel, _noop_teardown

    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    pg_event_store: EventStore = PostgresEventStore(pool)
    pg_idempotency_store: IdempotencyStore = PostgresIdempotencyStore(pool)
    authz = authorize_factory(
        settings,
        pg_event_store,
        pool=pool,
        clock=clock,
        id_generator=id_generator,
    )
    clearance_lookup: ClearanceLookup = (
        clearance_lookup_factory(pool)
        if clearance_lookup_factory is not None
        else AlwaysCoveredClearanceLookup()
    )
    caution_lookup: CautionLookup = (
        caution_lookup_factory(pool)
        if caution_lookup_factory is not None
        else AlwaysQuietCautionLookup()
    )
    supply_lookup: SupplyLookup = (
        supply_lookup_factory(pool)
        if supply_lookup_factory is not None
        else AllSatisfiedSupplyLookup()
    )
    credential_lookup: CredentialLookup = (
        credential_lookup_factory(pool)
        if credential_lookup_factory is not None
        else InMemoryCredentialLookup()
    )
    llm: LLM | None = llm_factory(settings) if llm_factory is not None else None
    kernel = make_postgres_kernel(
        pool,
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authz=authz,
        event_store=pg_event_store,
        idempotency_store=pg_idempotency_store,
        clearance_lookup=clearance_lookup,
        caution_lookup=caution_lookup,
        supply_lookup=supply_lookup,
        credential_lookup=credential_lookup,
        llm=llm,
        token_verifier=token_verifier,
    )
    return kernel, _compose_teardowns([_maybe_llm_teardown(llm), _make_pool_teardown(pool)])


async def _noop_teardown() -> None:
    return None


def _make_pool_teardown(pool: asyncpg.Pool) -> Teardown:
    async def teardown() -> None:
        await pool.close()

    return teardown


def _maybe_llm_teardown(llm: LLM | None) -> Teardown:
    """Build a teardown that closes the LLM client if it exposes `aclose()`.

    Production `AnthropicLLM` has an `aclose()` method that
    releases the SDK's httpx connection pool. Test stubs
    (`FakeLLM`) typically don't; the teardown is a no-op
    in that case. When `llm is None` (no LLM configured), the
    returned teardown is also a no-op.
    """

    async def teardown() -> None:
        if llm is None:
            return
        close = getattr(llm, "aclose", None)
        if close is None:
            return
        await close()

    return teardown


def _compose_teardowns(teardowns: list[Teardown]) -> Teardown:
    """Run teardowns sequentially, swallowing per-teardown errors.

    Ordering: pass `[a, b, c]` and they run a -> b -> c at shutdown.
    Errors from any one teardown are captured and re-raised AFTER
    the remaining teardowns run, so a misbehaving LLM client close
    doesn't leak the Postgres pool (or vice versa). The first
    raised exception wins; subsequent ones are suppressed per
    FastAPI shutdown convention.

    Catches `Exception` (NOT `BaseException`) so `asyncio.CancelledError`
    + `KeyboardInterrupt` + `SystemExit` propagate through the
    teardown chain as intended (architecture gate-review).
    """

    async def composed() -> None:
        first_exc: Exception | None = None
        for td in teardowns:
            try:
                await td()
            except Exception as exc:
                if first_exc is None:
                    first_exc = exc
        if first_exc is not None:
            raise first_exc

    return composed


__all__ = [
    "AuthorizeFactory",
    "CautionLookupFactory",
    "ClearanceLookupFactory",
    "CredentialLookupFactory",
    "LLMFactory",
    "build_kernel",
    "make_inmemory_kernel",
    "make_postgres_kernel",
]
