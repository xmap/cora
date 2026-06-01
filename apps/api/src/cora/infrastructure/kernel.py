"""Process-wide dependency kernel.

`Kernel` carries the cross-BC primitives (settings, clock,
id_generator, authorize, event_store, idempotency_store) plus the
asyncpg `pool` (None for `app_env=test`). It's the "Shared Kernel"
in the DDD sense: a deliberately-shared set of dependencies every
bounded context's `wire_<bc>(deps)` function pulls from.

## Why this lives in its own module

This module has **zero BC imports**. That's the point: every BC's
wire / handler / route imports `Kernel` from here without
transitively pulling in any other BC. Phase-8d hardening: the
prior `Kernel` (then `SharedDeps`) lived alongside the production-
construction logic that lazy-imported `cora.trust` for the
authorize factory. That lazy import was tagged `deprecated = true`
in tach.toml because tach couldn't tell that the import was
control-flow-guarded. Splitting the data class out of the
construction module breaks the cycle at the namespace level:
`cora.infrastructure.kernel` only knows about ports, not adapters.

## BC-specific stores stay BC-internal

`Kernel` carries cross-BC primitives only. BC-specific entry
stores (Trust BC's `TraversalStore`, Decision BC's `ReasoningStore`,
etc.) are constructed inside each BC's own `wire_<bc>(deps)` from
`deps.pool` and live BC-internal. This keeps the kernel clean as
more BCs adopt the logbook-and-entries pattern.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import asyncpg

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.signing_registry import SigningRegistry
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    LLM,
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
    Signer,
    SupplyLookup,
    TokenVerifier,
)
from cora.infrastructure.ports.federation import (
    PermitLookup,
    PublishPort,
    SignaturePort,
)


@dataclass(frozen=True)
class Kernel:
    """Process-wide dependencies. Immutable after construction.

    `pool` is the asyncpg connection pool (None when
    `app_env=test`). BCs that need additional Postgres-backed
    adapters (entry stores, projections, etc.) construct them in
    their own `wire_<bc>(deps)` from this pool, keeping BC-specific
    stores out of the kernel.

    `clearance_lookup`: cross-BC port consumed by
    Run BC's `start_run` handler to gate Run.start on the presence
    of an Active Safety Clearance covering the Run's scope. Safety
    BC ships `PostgresClearanceLookup` as the production adapter
    (reads `proj_safety_clearance_summary`). Test environments
    default to `AlwaysCoveredClearanceLookup` (synthetic Active
    clearance bypass) so existing Run tests don't have to seed
    real clearances; gate-specific tests override with the real
    adapter explicitly. Mirrors the `Authorize` / `AllowAllAuthorize`
    test-default pattern.

    `caution_lookup`: cross-BC port consumed by Run
    BC's `start_run` handler to snapshot operator-authored cautions
    onto the `RunStarted` event payload. Caution BC ships
    `PostgresCautionLookup` as the production adapter (reads
    `proj_caution_summary`). Test environments default to
    `AlwaysQuietCautionLookup` (returns `[]`) so existing Run tests
    don't have to seed cautions; snapshot-specific tests override
    with the real adapter explicitly. NON-BLOCKING by construction
    (see `cora.infrastructure.ports.caution_lookup` module
    docstring): the snapshot informs the payload but the decider
    never gates on it.

    `supply_lookup`: cross-BC port consumed by Run BC's `start_run`
    handler and Operation BC's `start_procedure` handler to gate
    start on Method.needed_supplies satisfaction (at least one
    AVAILABLE Supply per required kind). Supply BC ships
    `PostgresSupplyLookup` as the production adapter (reads
    `proj_supply_summary`, excludes Decommissioned rows per the
    partial UNIQUE INDEX semantics in
    [[project_deregister_supply_design]]). Test environments default
    to `AllSatisfiedSupplyLookup` (synthetic Available per kind) so
    existing Run / Procedure tests don't have to seed real Supplies;
    gate-specific tests override with the real adapter or with
    `NoSuppliesRegisteredLookup` for the missing-kind path. Mirrors
    the `ClearanceLookup` / `CautionLookup` test-default pattern.
    See [[project_supply_preflight_gate_design]].

    `credential_lookup`: cross-BC port consumed by Federation BC's
    seal handlers (`initialize_seal`, `rotate_seal_online_key`) to
    validate cross-aggregate purpose binding (the referenced
    Credential's purpose must match the seal slot:
    `SealOnlineSigning` for `online_credential_id`, `SealOfflineRoot` for
    `offline_credential_id`) and the status-Active invariant (Rotating or
    Revoked secrets cannot back a Seal). Federation BC ships
    `PostgresCredentialLookup` as the production adapter (reads
    `proj_federation_credential_summary` keyed by `credential_id`).
    Test environments default to `InMemoryCredentialLookup`; seal
    handler / decider tests seed credentials explicitly via the
    adapter's `register(...)` helper. The handler does the async
    lookup and threads the result through to the decider as part of
    the slice's context dataclass, keeping the decider pure (mirrors
    the start_run -> ClearanceLookup pattern).

    `llm`: optional LLM-chat port consumed by Agent BC subscribers
    (RunDebriefer, CautionDrafter). Production wires
    `AnthropicLLM` when `Settings.anthropic_api_key` is set;
    otherwise this is `None` and subscribers that depend on it must
    short-circuit or fail fast at registration time. Tests use
    `FakeLLM` (zero network) when an LLM is needed and leave
    this `None` otherwise.

    `logbook_mirror`: optional mirror to operator-facing logbook
    systems (Olog / SciLog / SciCat). No production implementor
    yet; the field exists to reserve the wiring slot and let the
    RunDebriefer subscriber short-circuit cleanly on `is None`. An
    adapter lands when a pilot facility's logbook is wired.

    `token_verifier`: process-singleton
    `TokenVerifier` (concretely `IdentityProviderRegistry`) built
    from `Settings.identity_providers`. `None` when no IdPs are
    configured (today's default): the legacy
    `X-Principal-Id`-with-`SYSTEM`-fallback path stays in effect.
    Non-`None` is the production-edge-auth posture: middleware
    extracts `Authorization: Bearer <token>`, verifies via this
    port, stores the resulting `VerifiedPrincipal` on the request
    state. Typed as the port (not the registry adapter) so the
    kernel-construction primitives can stay in
    `cora.infrastructure.deps` without `cora.infrastructure.kernel`
    importing `cora.infrastructure.auth` (kernel boundary: ports
    only, no adapters).

    `profile_store`: process-singleton `ProfileStore` for the
    `actor_profile` PII vault. Required (not optional) because
    BOTH Access BC (`register_actor`) AND Agent BC (`define_agent`)
    upsert through it on the genesis path — a missing
    profile_store breaks the cross-BC atomic write. Constructed in
    `make_*_kernel` as `PostgresProfileStore(pool)` (production)
    or `InMemoryProfileStore()` (tests / `app_env=test`). The
    Protocol lives in `cora.infrastructure.ports.profile_store`;
    adapters in `cora.access.aggregates.actor.profile`. Sibling-
    BC instances all read this one field so the in-memory dict is
    shared across slices, mirroring how `EventStore` and
    `IdempotencyStore` are shared.
    """

    settings: Settings
    clock: Clock
    id_generator: IdGenerator
    authz: Authorize
    event_store: EventStore
    idempotency_store: IdempotencyStore
    clearance_lookup: ClearanceLookup
    caution_lookup: CautionLookup
    supply_lookup: SupplyLookup
    credential_lookup: CredentialLookup
    profile_store: ProfileStore
    canonicalization_registry: CanonicalizationRegistry
    signing_registry: SigningRegistry
    pool: asyncpg.Pool | None = None
    llm: LLM | None = None
    logbook_mirror: LogbookMirror | None = None
    token_verifier: TokenVerifier | None = None
    signer: Signer | None = None
    publish_port: PublishPort | None = None
    signature_port: SignaturePort | None = None
    permit_lookup: PermitLookup | None = None


Teardown = Callable[[], Awaitable[None]]
"""Async callable returned by kernel-construction; the FastAPI
lifespan calls this to release pool resources at shutdown."""


__all__ = [
    "Kernel",
    "Teardown",
]
