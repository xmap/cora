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

from typing import TYPE_CHECKING, Protocol

import asyncpg

if TYPE_CHECKING:
    from collections.abc import Callable

    from cora.infrastructure.ports.federation import (
        PermitLookup,
        PublishPort,
        SignaturePort,
    )
    from cora.infrastructure.ports.signer import Signer

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.default_canonicalization_adapter import (
    DefaultCanonicalizationAdapter,
)
from cora.infrastructure.adapters.in_memory_assembly_lookup import InMemoryAssemblyLookup
from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.adapters.in_memory_clearance_template_lookup import (
    InMemoryClearanceTemplateLookup,
)
from cora.infrastructure.adapters.in_memory_credential_lookup import InMemoryCredentialLookup
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.adapters.in_memory_family_lookup import InMemoryFamilyLookup
from cora.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
from cora.infrastructure.adapters.in_memory_profile_store import InMemoryProfileStore
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
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
    AllocationLookup,
    AllSatisfiedSupplyLookup,
    AlwaysApprovedLanguageModelLookup,
    AlwaysCoveredClearanceLookup,
    AlwaysEmptyCapabilityLookup,
    AlwaysEmptyModelUsageLookup,
    AlwaysPermittedEnclosureLookup,
    AlwaysQuietCautionLookup,
    AlwaysRatifiedConsequenceLookup,
    AlwaysZeroSpendLookup,
    AssemblyLookup,
    AssetLookup,
    Authorize,
    CapabilityLookup,
    CautionLookup,
    ClearanceLookup,
    ClearanceTemplateLookup,
    Clock,
    ComputeReachabilityLookup,
    ConsequenceLookup,
    CredentialLookup,
    DatasetDistributionLookup,
    EnclosureLookup,
    EventStore,
    FacilityLookup,
    FamilyLookup,
    IdempotencyStore,
    IdGenerator,
    LanguageModelLookup,
    LogbookMirror,
    ModelUsageLookup,
    NoActiveAllocationLookup,
    NoComputeReachabilityLookup,
    NoDatasetDistributionsLookup,
    NoInvolvementLookup,
    ProfileStore,
    RoleLookup,
    RunActorInvolvementLookup,
    SpendLookup,
    SupplyLookup,
    SystemClock,
    TokenVerifier,
    UUIDv7Generator,
)
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.read_only_event_store import ReadOnlyEventStore
from cora.infrastructure.schema_version import SchemaPosture, verify_schema_version


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
    clearance_template_lookup: ClearanceTemplateLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    capability_lookup: CapabilityLookup | None = None,
    supply_lookup: SupplyLookup | None = None,
    spend_lookup: SpendLookup | None = None,
    run_actor_involvement_lookup: RunActorInvolvementLookup | None = None,
    consequence_lookup: ConsequenceLookup | None = None,
    dataset_distribution_lookup: DatasetDistributionLookup | None = None,
    compute_reachability_lookup: ComputeReachabilityLookup | None = None,
    credential_lookup: CredentialLookup | None = None,
    facility_lookup: FacilityLookup | None = None,
    asset_lookup: AssetLookup | None = None,
    family_lookup: FamilyLookup | None = None,
    assembly_lookup: AssemblyLookup | None = None,
    role_lookup: RoleLookup | None = None,
    enclosure_lookup: EnclosureLookup | None = None,
    language_model_lookup: LanguageModelLookup | None = None,
    model_usage_lookup: ModelUsageLookup | None = None,
    allocation_lookup: AllocationLookup | None = None,
    profile_store: ProfileStore | None = None,
    llm: LLM | None = None,
    logbook_mirror: LogbookMirror | None = None,
    token_verifier: TokenVerifier | None = None,
    signer: "Signer | None" = None,
    publish_port: "PublishPort | None" = None,
    signature_port: "SignaturePort | None" = None,
    permit_lookup: "PermitLookup | None" = None,
    schema_posture: SchemaPosture = "matched",
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

    `schema_posture` REPORTS what the caller already decided; it does not
    enforce anything here. `build_kernel` is what checks the applied
    schema version and wraps the store in `ReadOnlyEventStore` before
    handing it over, so passing `"degraded"` alongside the default
    `event_store=None` yields a degraded posture over a WRITABLE store.
    Nothing in production does that (build_kernel always passes both
    together), and this parameter exists so the posture reaches
    `/readyz`, not as a second way to turn writes off.

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

    `capability_lookup` defaults to `AlwaysEmptyCapabilityLookup`
    (returns `[]`) so existing Equipment integration tests don't
    have to seed Capability projection rows. Production's
    `build_kernel` injects the real `PostgresCapabilityLookup` via
    the `capability_lookup_factory` argument; surface-specific
    tests override here explicitly with a fake returning seeded
    references or with the real adapter.

    `supply_lookup` defaults to `AllSatisfiedSupplyLookup` (synthetic
    Available per requested kind) so existing Run / Procedure tests
    don't have to seed real Supplies. Production's `build_kernel`
    injects the real `PostgresSupplyLookup` via the
    `supply_lookup_factory` argument; gate-specific tests override
    here explicitly. See [[project_supply_preflight_gate_design]].

    `spend_lookup` and `allocation_lookup` default to the disarmed
    stubs (`AlwaysZeroSpendLookup` / `NoActiveAllocationLookup`) here,
    the same opt-in posture as every other lookup: an integration test
    that does not exercise the envelope never meters or gates on it.
    The fail-loud requirement lives one layer up, in `build_kernel`'s
    Postgres branch, which raises when either financial factory is
    missing so a real deployment can never silently meter zero.

    `run_actor_involvement_lookup` defaults to `NoInvolvementLookup`
    (returns `[]`) so existing tests don't have to seed runs.
    Production's `build_kernel` injects the real
    `PostgresRunActorInvolvementLookup` via the
    `run_actor_involvement_lookup_factory` argument; kill-switch tests
    override here explicitly.

    `dataset_distribution_lookup` defaults to `NoDatasetDistributionsLookup`
    (every Dataset has no Distribution): the conservative default for the
    genesis-only input gate, so a Run declaring an input but seeding
    nothing fails. Production's `build_kernel` injects the real
    `PostgresDatasetDistributionLookup` via the
    `dataset_distribution_lookup_factory` argument; gate-specific tests
    override here with `SeededDatasetDistributionLookup`. See
    [[project_run_input_dependency_design]].

    `compute_reachability_lookup` defaults to `NoComputeReachabilityLookup`
    (every code unknown): the conservative default for the reachability arm
    of the input gate, so a Run naming a compute resource fails with
    `RunComputeResourceUnknownError` unless seeded. The production adapter is
    deferred; gate-specific tests override here with
    `SeededComputeReachabilityLookup`. Runs naming no compute resource never
    call the lookup, so the arm is dormant.

    `credential_lookup` defaults to a fresh `InMemoryCredentialLookup`
    (empty record map). Seal handler / decider tests seed credentials
    explicitly via the adapter's `register(...)` helper; non-Seal
    tests never touch it, so an empty default is safe. Production's
    `build_kernel` injects the real `PostgresCredentialLookup` via the
    `credential_lookup_factory` argument.

    `facility_lookup` defaults to a fresh `InMemoryFacilityLookup`
    (empty record map). register_facility-with-parent + future
    add_facility_trust_anchor_credential tests seed facilities
    explicitly via the adapter's `register(...)` helper; tests that
    register only Site facilities (parent_id=None) never touch it.
    Production's `build_kernel` injects the real
    `PostgresFacilityLookup` via the `facility_lookup_factory` argument.

    `asset_lookup` defaults to a fresh `InMemoryAssetLookup` (empty
    record map). Cross-BC binding tests (Slice 7B Supply
    `containing_asset_id` validation, future Slice 8 Asset
    `facility_id` binding, future Safety / Caution BC consumers) seed
    assets explicitly via the adapter's `register(...)` helper; tests
    that don't bind to an Asset never touch it. Production's
    `build_kernel` injects the real `PostgresAssetLookup` via the
    `asset_lookup_factory` argument.

    `family_lookup` defaults to a fresh `InMemoryFamilyLookup` (empty
    record map). Layer-3 consumer tests (3D `bind_plan_role`
    role_kind satisfaction path) seed Families explicitly via the
    adapter's `register(...)` helper; tests that don't bind via
    role_kind never touch it. Production's `build_kernel` injects
    the real `PostgresFamilyLookup` via the `family_lookup_factory`
    argument.

    `role_lookup` defaults to a fresh `InMemoryRoleLookup` (empty
    record map). Layer-3 consumer tests (3B add_family_presents_as,
    3C add_assembly_presents_as, 3D bind_plan_role, 3E
    update_capability_suggested_roles) seed Roles explicitly via the
    adapter's `register(...)` helper; tests that don't touch a Role
    leave the dict empty (the default). Production's `build_kernel`
    injects the real `PostgresRoleLookup` via the
    `role_lookup_factory` argument.

    `language_model_lookup` defaults to `AlwaysApprovedLanguageModelLookup`
    (every identity Approved) so integration tests that never stood up
    a catalog keep the define_agent gate disarmed. Production's
    `build_kernel` injects the real `PostgresLanguageModelLookup` via
    the `language_model_lookup_factory` argument; gate-specific tests
    override here explicitly.

    `model_usage_lookup` defaults to `AlwaysEmptyModelUsageLookup` (no
    recorded call touched any model) so tests that don't exercise the
    at-risk-results surface stay inert. Production's `build_kernel`
    injects the real `PostgresModelUsageLookup` via the
    `model_usage_lookup_factory` argument; slice-specific tests
    override here explicitly.

    `llm` defaults to `None` because most BCs and tests don't need
    an LLM; only Agent BC subscribers consume it. Production's
    `build_kernel` injects `AnthropicLLM` when both
    `Settings.llm_enabled` and `Settings.anthropic_api_key` are
    set; subscriber-level tests inject `FakeLLM` explicitly.

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
        schema_posture=schema_posture,
        event_store=event_store if event_store is not None else PostgresEventStore(pool),
        idempotency_store=(
            idempotency_store if idempotency_store is not None else PostgresIdempotencyStore(pool)
        ),
        clearance_lookup=(
            clearance_lookup if clearance_lookup is not None else AlwaysCoveredClearanceLookup()
        ),
        clearance_template_lookup=(
            clearance_template_lookup
            if clearance_template_lookup is not None
            else InMemoryClearanceTemplateLookup()
        ),
        caution_lookup=(
            caution_lookup if caution_lookup is not None else AlwaysQuietCautionLookup()
        ),
        capability_lookup=(
            capability_lookup if capability_lookup is not None else AlwaysEmptyCapabilityLookup()
        ),
        supply_lookup=(supply_lookup if supply_lookup is not None else AllSatisfiedSupplyLookup()),
        spend_lookup=(spend_lookup if spend_lookup is not None else AlwaysZeroSpendLookup()),
        run_actor_involvement_lookup=(
            run_actor_involvement_lookup
            if run_actor_involvement_lookup is not None
            else NoInvolvementLookup()
        ),
        consequence_lookup=(
            consequence_lookup
            if consequence_lookup is not None
            else AlwaysRatifiedConsequenceLookup()
        ),
        dataset_distribution_lookup=(
            dataset_distribution_lookup
            if dataset_distribution_lookup is not None
            else NoDatasetDistributionsLookup()
        ),
        compute_reachability_lookup=(
            compute_reachability_lookup
            if compute_reachability_lookup is not None
            else NoComputeReachabilityLookup()
        ),
        credential_lookup=(
            credential_lookup if credential_lookup is not None else InMemoryCredentialLookup()
        ),
        facility_lookup=(
            facility_lookup if facility_lookup is not None else InMemoryFacilityLookup()
        ),
        asset_lookup=(asset_lookup if asset_lookup is not None else InMemoryAssetLookup()),
        family_lookup=(family_lookup if family_lookup is not None else InMemoryFamilyLookup()),
        assembly_lookup=(
            assembly_lookup if assembly_lookup is not None else InMemoryAssemblyLookup()
        ),
        role_lookup=(role_lookup if role_lookup is not None else InMemoryRoleLookup()),
        enclosure_lookup=(
            enclosure_lookup if enclosure_lookup is not None else AlwaysPermittedEnclosureLookup()
        ),
        language_model_lookup=(
            language_model_lookup
            if language_model_lookup is not None
            else AlwaysApprovedLanguageModelLookup()
        ),
        model_usage_lookup=(
            model_usage_lookup if model_usage_lookup is not None else AlwaysEmptyModelUsageLookup()
        ),
        allocation_lookup=(
            allocation_lookup if allocation_lookup is not None else NoActiveAllocationLookup()
        ),
        profile_store=(profile_store if profile_store is not None else PostgresProfileStore(pool)),
        canonicalization_registry=_build_default_canonicalization_registry(),
        signing_registry=SigningRegistry(),
        publish_port=publish_port,
        signature_port=signature_port,
        signer=signer,
        permit_lookup=permit_lookup,
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
    clearance_template_lookup: ClearanceTemplateLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    capability_lookup: CapabilityLookup | None = None,
    supply_lookup: SupplyLookup | None = None,
    spend_lookup: SpendLookup | None = None,
    run_actor_involvement_lookup: RunActorInvolvementLookup | None = None,
    consequence_lookup: ConsequenceLookup | None = None,
    dataset_distribution_lookup: DatasetDistributionLookup | None = None,
    compute_reachability_lookup: ComputeReachabilityLookup | None = None,
    credential_lookup: CredentialLookup | None = None,
    facility_lookup: FacilityLookup | None = None,
    asset_lookup: AssetLookup | None = None,
    family_lookup: FamilyLookup | None = None,
    assembly_lookup: AssemblyLookup | None = None,
    role_lookup: RoleLookup | None = None,
    enclosure_lookup: EnclosureLookup | None = None,
    language_model_lookup: LanguageModelLookup | None = None,
    model_usage_lookup: ModelUsageLookup | None = None,
    allocation_lookup: AllocationLookup | None = None,
    profile_store: ProfileStore | None = None,
    llm: LLM | None = None,
    logbook_mirror: LogbookMirror | None = None,
    token_verifier: TokenVerifier | None = None,
    signer: "Signer | None" = None,
    publish_port: "PublishPort | None" = None,
    signature_port: "SignaturePort | None" = None,
    permit_lookup: "PermitLookup | None" = None,
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

    `capability_lookup` defaults to `AlwaysEmptyCapabilityLookup`
    (returns `[]`) for the same reason: no projection worker, no
    `proj_recipe_capability_summary` table. Surface-specific tests
    override with a fake returning seeded references or with the
    real adapter.

    `supply_lookup` defaults to `AllSatisfiedSupplyLookup` for the same
    reason: no projection worker, no `proj_supply_summary` table to
    read from. Gate-specific tests can override with
    `NoSuppliesRegisteredLookup` (missing-kind path) or a custom fake.

    `run_actor_involvement_lookup` defaults to `NoInvolvementLookup`
    (returns `[]`) for the same reason: no projection worker, no
    `proj_run_actor_involvement` table to read from. Kill-switch tests
    can override with a custom fake or the real adapter.

    `dataset_distribution_lookup` defaults to `NoDatasetDistributionsLookup`
    for the same reason: no projection worker, no
    `proj_data_distribution_summary` table to read from. The default is
    conservative (every Dataset has no Distribution), so a Run declaring
    an input fails the genesis input gate unless the test overrides with
    `SeededDatasetDistributionLookup`. Ordinary Runs declare no inputs,
    so the gate is dormant. See [[project_run_input_dependency_design]].

    `compute_reachability_lookup` defaults to `NoComputeReachabilityLookup`
    (every code unknown): the conservative default for the reachability arm
    of the input gate. A Run naming a compute resource fails with
    `RunComputeResourceUnknownError` unless the test overrides with
    `SeededComputeReachabilityLookup`. Runs naming no compute resource never
    call the lookup, so the arm is dormant. The production adapter (a
    deployment-config map resolved by Supply name) is deferred.

    `credential_lookup` defaults to a fresh `InMemoryCredentialLookup`
    for the same reason: no projection worker, no
    `proj_federation_credential_summary` table to read from. Seal
    handler / decider tests seed credentials via the adapter's
    `register(...)` helper; tests that don't touch the seal slices
    leave the dict empty (the default).

    `facility_lookup` defaults to a fresh `InMemoryFacilityLookup`
    for the same reason: no projection worker, no
    `proj_federation_facility_summary` table to read from.
    register_facility-with-parent + future trust-anchor-add tests
    seed facilities via the adapter's `register(...)` helper; tests
    that register only Site facilities (parent_id=None) never touch it.

    `asset_lookup` defaults to a fresh `InMemoryAssetLookup` for the
    same reason: no projection worker, no
    `proj_equipment_asset_summary` table to read from. Cross-BC
    binding tests (Slice 7B Supply, future Slice 8 Asset.facility_id,
    future Safety / Caution BC consumers) seed assets via the
    adapter's `register(...)` helper; tests that don't bind to an
    Asset never touch it.

    `family_lookup` defaults to a fresh `InMemoryFamilyLookup` for
    the same reason: no projection worker, no
    `proj_equipment_family_summary` table to read from. Layer-3
    consumer tests (3D `bind_plan_role`) seed Families via the
    adapter's `register(...)` helper; tests that don't bind via
    role_kind leave the dict empty (the default).

    `role_lookup` defaults to a fresh `InMemoryRoleLookup` for the
    same reason: no projection worker, no `proj_equipment_role_summary`
    table to read from. Layer-3 consumer tests seed Roles via the
    adapter's `register(...)` helper; tests that don't touch a Role
    leave the dict empty (the default).

    `language_model_lookup` defaults to `AlwaysApprovedLanguageModelLookup`
    (every identity Approved) for the same reason: no projection worker,
    no `proj_agent_language_model_summary` table to read from, and the
    define_agent gate must stay disarmed for every existing test.
    Gate-specific tests override with a fake returning None or a
    non-Approved entry.

    `model_usage_lookup` defaults to `AlwaysEmptyModelUsageLookup` (no
    recorded call touched any model) for the same reason: no Postgres,
    no `entries_decision_inferences` table to scan, and the at-risk
    read slice must stay inert for every test that doesn't exercise
    it. Slice-specific tests override with a fake returning seeded
    `ModelUsageLookupResult` rows.

    `allocation_lookup` defaults to `NoActiveAllocationLookup` (no
    envelope Active) for the same reason: no projection worker, no
    `proj_budget_allocation_summary` table to read from, and the
    envelope check must stay disarmed for every test that never
    declared an allocation. Envelope-gate tests override with a fake
    returning a chosen `AllocationLookupResult`.

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
        clearance_template_lookup=(
            clearance_template_lookup
            if clearance_template_lookup is not None
            else InMemoryClearanceTemplateLookup()
        ),
        caution_lookup=(
            caution_lookup if caution_lookup is not None else AlwaysQuietCautionLookup()
        ),
        capability_lookup=(
            capability_lookup if capability_lookup is not None else AlwaysEmptyCapabilityLookup()
        ),
        supply_lookup=(supply_lookup if supply_lookup is not None else AllSatisfiedSupplyLookup()),
        spend_lookup=(spend_lookup if spend_lookup is not None else AlwaysZeroSpendLookup()),
        run_actor_involvement_lookup=(
            run_actor_involvement_lookup
            if run_actor_involvement_lookup is not None
            else NoInvolvementLookup()
        ),
        consequence_lookup=(
            consequence_lookup
            if consequence_lookup is not None
            else AlwaysRatifiedConsequenceLookup()
        ),
        dataset_distribution_lookup=(
            dataset_distribution_lookup
            if dataset_distribution_lookup is not None
            else NoDatasetDistributionsLookup()
        ),
        compute_reachability_lookup=(
            compute_reachability_lookup
            if compute_reachability_lookup is not None
            else NoComputeReachabilityLookup()
        ),
        credential_lookup=(
            credential_lookup if credential_lookup is not None else InMemoryCredentialLookup()
        ),
        facility_lookup=(
            facility_lookup if facility_lookup is not None else InMemoryFacilityLookup()
        ),
        asset_lookup=(asset_lookup if asset_lookup is not None else InMemoryAssetLookup()),
        family_lookup=(family_lookup if family_lookup is not None else InMemoryFamilyLookup()),
        assembly_lookup=(
            assembly_lookup if assembly_lookup is not None else InMemoryAssemblyLookup()
        ),
        role_lookup=(role_lookup if role_lookup is not None else InMemoryRoleLookup()),
        enclosure_lookup=(
            enclosure_lookup if enclosure_lookup is not None else AlwaysPermittedEnclosureLookup()
        ),
        language_model_lookup=(
            language_model_lookup
            if language_model_lookup is not None
            else AlwaysApprovedLanguageModelLookup()
        ),
        model_usage_lookup=(
            model_usage_lookup if model_usage_lookup is not None else AlwaysEmptyModelUsageLookup()
        ),
        allocation_lookup=(
            allocation_lookup if allocation_lookup is not None else NoActiveAllocationLookup()
        ),
        profile_store=profile_store if profile_store is not None else InMemoryProfileStore(),
        canonicalization_registry=_build_default_canonicalization_registry(),
        signing_registry=SigningRegistry(),
        publish_port=publish_port,
        signature_port=signature_port,
        signer=signer,
        permit_lookup=permit_lookup,
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


class CapabilityLookupFactory(Protocol):
    """Builds the production CapabilityLookup port for the Kernel.

    Recipe BC's `cora.recipe.adapters.PostgresCapabilityLookup` is
    the production factory; `cora.api.main` binds it. Same
    factory-injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC (tach
    module rule: `cora.infrastructure depends_on = []`).

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysEmptyCapabilityLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> CapabilityLookup: ...


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


class SpendLookupFactory(Protocol):
    """Builds the production SpendLookup port for the Kernel.

    Decision BC's `cora.decision.adapters.PostgresSpendLookup` is the
    production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysZeroSpendLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> SpendLookup: ...


class LanguageModelLookupFactory(Protocol):
    """Builds the production LanguageModelLookup port for the Kernel.

    Agent BC's `cora.agent.adapters.PostgresLanguageModelLookup` is the
    production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysApprovedLanguageModelLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> LanguageModelLookup: ...


class AllocationLookupFactory(Protocol):
    """Builds the production AllocationLookup port for the Kernel.

    Budget BC's `cora.budget.adapters.PostgresAllocationLookup` is the
    production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `NoActiveAllocationLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> AllocationLookup: ...


class ModelUsageLookupFactory(Protocol):
    """Builds the production ModelUsageLookup port for the Kernel.

    Decision BC's `cora.decision.adapters.PostgresModelUsageLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysEmptyModelUsageLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> ModelUsageLookup: ...


class RunActorInvolvementLookupFactory(Protocol):
    """Builds the production RunActorInvolvementLookup port for the Kernel.

    Run BC's `cora.run.adapters.PostgresRunActorInvolvementLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to `NoInvolvementLookup`
    automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> RunActorInvolvementLookup: ...


class ConsequenceLookupFactory(Protocol):
    """Builds the production ConsequenceLookup port for the Kernel.

    Trust BC's `cora.trust.adapters.PostgresConsequenceLookup` is the
    production factory; `cora.api.main` binds it. Same factory-injection
    shape as the other lookup factories so `cora.infrastructure.deps`
    doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `AlwaysRatifiedConsequenceLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> ConsequenceLookup: ...


class DatasetDistributionLookupFactory(Protocol):
    """Builds the production DatasetDistributionLookup port for the Kernel.

    Data BC's `cora.data.adapters.PostgresDatasetDistributionLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as the other lookup factories so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to
    `NoDatasetDistributionsLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> DatasetDistributionLookup: ...


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


class FacilityLookupFactory(Protocol):
    """Builds the production FacilityLookup port for the Kernel.

    Federation BC's `cora.federation.adapters.PostgresFacilityLookup`
    is the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `CredentialLookupFactory` so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryFacilityLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> FacilityLookup: ...


class AssetLookupFactory(Protocol):
    """Builds the production AssetLookup port for the Kernel.

    Equipment BC's `cora.equipment.adapters.PostgresAssetLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `FacilityLookupFactory` /
    `CredentialLookupFactory` so `cora.infrastructure.deps` doesn't
    import from any BC (tach module rule:
    `cora.infrastructure depends_on = []`).

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryAssetLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> AssetLookup: ...


class FamilyLookupFactory(Protocol):
    """Builds the production FamilyLookup port for the Kernel.

    Equipment BC's `cora.equipment.adapters.PostgresFamilyLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `AssetLookupFactory` so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryFamilyLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> FamilyLookup: ...


class AssemblyLookupFactory(Protocol):
    """Builds the production AssemblyLookup port for the Kernel.

    Equipment BC's `cora.equipment.adapters.PostgresAssemblyLookup`
    is the production factory; `cora.api.main` binds it. Same
    factory-injection shape as `FamilyLookupFactory`.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryAssemblyLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> AssemblyLookup: ...


class RoleLookupFactory(Protocol):
    """Builds the production RoleLookup port for the Kernel.

    Equipment BC's `cora.equipment.adapters.PostgresRoleLookup` is
    the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `AssetLookupFactory` so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryRoleLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> RoleLookup: ...


class ClearanceTemplateLookupFactory(Protocol):
    """Builds the production ClearanceTemplateLookup port for the Kernel.

    Safety BC's `cora.safety.adapters.PostgresClearanceTemplateLookup`
    is the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `AssetLookupFactory` so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `InMemoryClearanceTemplateLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> ClearanceTemplateLookup: ...


class EnclosureLookupFactory(Protocol):
    """Builds the production EnclosureLookup port for the Kernel.

    Enclosure BC's `cora.enclosure.adapters.PostgresEnclosureLookup`
    is the production factory; `cora.api.main` binds it. Same factory-
    injection shape as `FacilityLookupFactory` so
    `cora.infrastructure.deps` doesn't import from any BC.

    `pool` is `None` only when `app_env=test`; the production factory
    requires a real pool. Test mode falls back to a fresh
    `AlwaysPermittedEnclosureLookup` automatically.
    """

    def __call__(
        self,
        pool: asyncpg.Pool,
    ) -> EnclosureLookup: ...


class LLMFactory(Protocol):
    """Builds the production LLM for the Kernel.

    Agent BC's `cora.agent.adapters.AnthropicLLM` is the
    only production factory today; `cora.api.main` binds it when
    BOTH `Settings.llm_enabled` (the switch, default off) and
    `Settings.anthropic_api_key` (the credential) are set. Same factory-injection
    shape as `AuthorizeFactory` / `ClearanceLookupFactory` /
    `CautionLookupFactory` so `cora.infrastructure.deps` doesn't
    import from any BC (tach module rule:
    `cora.infrastructure depends_on = []`).

    `settings` is passed (rather than just an API key) so the
    factory can read provider-specific options (timeouts,
    max_retries, base URL overrides) without growing the factory
    surface every time. The factory's `__call__` returns `None`
    when settings indicate no LLM should be wired (the switch off,
    or no credential) so the Kernel ends up with `llm=None`. The
    LLM-backed Agent subscribers then log a warning and SKIP
    registration; they do not fail-fast, so a deployment may defer
    Agent rollout without refusing to boot.
    """

    def __call__(
        self,
        settings: Settings,
    ) -> LLM | None: ...


async def build_kernel(
    *,
    authorize_factory: AuthorizeFactory,
    clearance_lookup_factory: ClearanceLookupFactory | None = None,
    clearance_template_lookup_factory: ClearanceTemplateLookupFactory | None = None,
    caution_lookup_factory: CautionLookupFactory | None = None,
    capability_lookup_factory: CapabilityLookupFactory | None = None,
    supply_lookup_factory: SupplyLookupFactory | None = None,
    spend_lookup_factory: SpendLookupFactory | None = None,
    language_model_lookup_factory: LanguageModelLookupFactory | None = None,
    model_usage_lookup_factory: ModelUsageLookupFactory | None = None,
    allocation_lookup_factory: AllocationLookupFactory | None = None,
    run_actor_involvement_lookup_factory: RunActorInvolvementLookupFactory | None = None,
    consequence_lookup_factory: ConsequenceLookupFactory | None = None,
    dataset_distribution_lookup_factory: DatasetDistributionLookupFactory | None = None,
    credential_lookup_factory: CredentialLookupFactory | None = None,
    facility_lookup_factory: FacilityLookupFactory | None = None,
    asset_lookup_factory: AssetLookupFactory | None = None,
    family_lookup_factory: FamilyLookupFactory | None = None,
    assembly_lookup_factory: AssemblyLookupFactory | None = None,
    role_lookup_factory: RoleLookupFactory | None = None,
    enclosure_lookup_factory: EnclosureLookupFactory | None = None,
    publish_port_factory: "Callable[[], PublishPort] | None" = None,
    signature_port_factory: "Callable[[], SignaturePort] | None" = None,
    signer_factory: "Callable[[], Signer] | None" = None,
    permit_lookup_factory: "Callable[[], PermitLookup] | None" = None,
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
            publish_port=publish_port_factory() if publish_port_factory is not None else None,
            signature_port=signature_port_factory() if signature_port_factory is not None else None,
            signer=signer_factory() if signer_factory is not None else None,
            permit_lookup=permit_lookup_factory() if permit_lookup_factory is not None else None,
        )
        return kernel, _noop_teardown

    if spend_lookup_factory is None or allocation_lookup_factory is None:
        # Fail loud, not open: a Postgres deployment that silently fell back
        # to the zero-spend stub and the no-active-envelope stub would meter
        # every call at $0 and disarm the instrument ceiling, and every seal
        # would record $0 as the official closing figure. The financial
        # lookups are the one place a missing binding must stop startup.
        raise ValueError(
            "build_kernel requires spend_lookup_factory and "
            "allocation_lookup_factory in a Postgres deployment; a missing "
            "financial lookup would silently meter zero and disarm the "
            "spend envelope"
        )
    pool = await create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    # Before anything can write. A mismatched schema is what a restore
    # leaves behind, and an append made against one is history rather
    # than a row to correct later. Raising here fails the lifespan, which
    # exits the process with the remedy on stderr.
    schema = await verify_schema_version(
        pool, allow_mismatch=settings.allow_schema_version_mismatch
    )
    pg_event_store: EventStore = PostgresEventStore(pool)
    if schema.posture == "degraded":
        pg_event_store = ReadOnlyEventStore(
            pg_event_store, applied=schema.applied, expected=schema.expected
        )
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
    capability_lookup: CapabilityLookup = (
        capability_lookup_factory(pool)
        if capability_lookup_factory is not None
        else AlwaysEmptyCapabilityLookup()
    )
    supply_lookup: SupplyLookup = (
        supply_lookup_factory(pool)
        if supply_lookup_factory is not None
        else AllSatisfiedSupplyLookup()
    )
    # Non-None guaranteed by the fail-loud guard above.
    spend_lookup: SpendLookup = spend_lookup_factory(pool)
    language_model_lookup: LanguageModelLookup = (
        language_model_lookup_factory(pool)
        if language_model_lookup_factory is not None
        else AlwaysApprovedLanguageModelLookup()
    )
    model_usage_lookup: ModelUsageLookup = (
        model_usage_lookup_factory(pool)
        if model_usage_lookup_factory is not None
        else AlwaysEmptyModelUsageLookup()
    )
    # Non-None guaranteed by the fail-loud guard above.
    allocation_lookup: AllocationLookup = allocation_lookup_factory(pool)
    run_actor_involvement_lookup: RunActorInvolvementLookup = (
        run_actor_involvement_lookup_factory(pool)
        if run_actor_involvement_lookup_factory is not None
        else NoInvolvementLookup()
    )
    consequence_lookup: ConsequenceLookup = (
        consequence_lookup_factory(pool)
        if consequence_lookup_factory is not None
        else AlwaysRatifiedConsequenceLookup()
    )
    dataset_distribution_lookup: DatasetDistributionLookup = (
        dataset_distribution_lookup_factory(pool)
        if dataset_distribution_lookup_factory is not None
        else NoDatasetDistributionsLookup()
    )
    credential_lookup: CredentialLookup = (
        credential_lookup_factory(pool)
        if credential_lookup_factory is not None
        else InMemoryCredentialLookup()
    )
    facility_lookup: FacilityLookup = (
        facility_lookup_factory(pool)
        if facility_lookup_factory is not None
        else InMemoryFacilityLookup()
    )
    asset_lookup: AssetLookup = (
        asset_lookup_factory(pool) if asset_lookup_factory is not None else InMemoryAssetLookup()
    )
    family_lookup: FamilyLookup = (
        family_lookup_factory(pool) if family_lookup_factory is not None else InMemoryFamilyLookup()
    )
    assembly_lookup: AssemblyLookup = (
        assembly_lookup_factory(pool)
        if assembly_lookup_factory is not None
        else InMemoryAssemblyLookup()
    )
    role_lookup: RoleLookup = (
        role_lookup_factory(pool) if role_lookup_factory is not None else InMemoryRoleLookup()
    )
    clearance_template_lookup: ClearanceTemplateLookup = (
        clearance_template_lookup_factory(pool)
        if clearance_template_lookup_factory is not None
        else InMemoryClearanceTemplateLookup()
    )
    enclosure_lookup: EnclosureLookup = (
        enclosure_lookup_factory(pool)
        if enclosure_lookup_factory is not None
        else AlwaysPermittedEnclosureLookup()
    )
    llm: LLM | None = llm_factory(settings) if llm_factory is not None else None
    kernel = make_postgres_kernel(
        pool,
        settings=settings,
        clock=clock,
        id_generator=id_generator,
        authz=authz,
        schema_posture=schema.posture,
        event_store=pg_event_store,
        idempotency_store=pg_idempotency_store,
        clearance_lookup=clearance_lookup,
        clearance_template_lookup=clearance_template_lookup,
        caution_lookup=caution_lookup,
        capability_lookup=capability_lookup,
        supply_lookup=supply_lookup,
        spend_lookup=spend_lookup,
        language_model_lookup=language_model_lookup,
        model_usage_lookup=model_usage_lookup,
        allocation_lookup=allocation_lookup,
        run_actor_involvement_lookup=run_actor_involvement_lookup,
        consequence_lookup=consequence_lookup,
        dataset_distribution_lookup=dataset_distribution_lookup,
        credential_lookup=credential_lookup,
        facility_lookup=facility_lookup,
        asset_lookup=asset_lookup,
        family_lookup=family_lookup,
        assembly_lookup=assembly_lookup,
        role_lookup=role_lookup,
        enclosure_lookup=enclosure_lookup,
        llm=llm,
        token_verifier=token_verifier,
        publish_port=publish_port_factory() if publish_port_factory is not None else None,
        signature_port=signature_port_factory() if signature_port_factory is not None else None,
        signer=signer_factory() if signer_factory is not None else None,
        permit_lookup=permit_lookup_factory() if permit_lookup_factory is not None else None,
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
    "AssemblyLookupFactory",
    "AssetLookupFactory",
    "AuthorizeFactory",
    "CapabilityLookupFactory",
    "CautionLookupFactory",
    "ClearanceLookupFactory",
    "ClearanceTemplateLookupFactory",
    "ConsequenceLookupFactory",
    "CredentialLookupFactory",
    "DatasetDistributionLookupFactory",
    "EnclosureLookupFactory",
    "FacilityLookupFactory",
    "FamilyLookupFactory",
    "LLMFactory",
    "LanguageModelLookupFactory",
    "ModelUsageLookupFactory",
    "RoleLookupFactory",
    "RunActorInvolvementLookupFactory",
    "SupplyLookupFactory",
    "build_kernel",
    "make_inmemory_kernel",
    "make_postgres_kernel",
]
