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
`cora.infrastructure.kernel` knows about ports, not adapters, with two
deliberate carve-outs: the `canonicalization_registry` and
`signing_registry` fields are concrete version-dispatch containers
(`CanonicalizationRegistry` / `SigningRegistry`) because version
selection needs the registry container, not a single port instance.

## BC-specific stores stay BC-internal

`Kernel` carries cross-BC primitives only. BC-specific entry
stores (Trust BC's `VerdictStore`, Decision BC's `InferenceStore`,
etc.) are constructed inside each BC's own `wire_<bc>(deps)` from
`deps.pool` and live BC-internal. This keeps the kernel clean as
more BCs adopt the logbook-and-entries pattern.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import asyncpg

from cora.infrastructure.adapters.canonicalization_registry import (
    CanonicalizationRegistry,
)
from cora.infrastructure.adapters.signing_registry import SigningRegistry
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import (
    LLM,
    AllBeamOpenLookup,
    AllocationLookup,
    AlwaysApprovedLanguageModelLookup,
    AlwaysEmptyModelUsageLookup,
    AlwaysGrantedSpendGuard,
    AssemblyLookup,
    AssetLookup,
    Authorize,
    BeamAvailabilityLookup,
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
    InferenceRecorder,
    LanguageModelLookup,
    LogbookMirror,
    ModelUsageLookup,
    NoActiveAllocationLookup,
    NullInferenceRecorder,
    ProfileStore,
    RoleLookup,
    RunActorInvolvementLookup,
    Signer,
    SpendGuard,
    SpendLookup,
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

    `clearance_template_lookup`: cross-aggregate port consumed by
    Safety BC's own `version_clearance_template` handler to validate
    the supersedes_template_id parent chain stays within one
    facility (per the cross-facility identity lock). 9E extends the
    consumer set with `register_clearance` / `amend_clearance`.
    Safety BC ships `PostgresClearanceTemplateLookup` as the
    production adapter (reads `proj_safety_clearance_template_summary`).
    Test environments default to `InMemoryClearanceTemplateLookup`;
    chain-validation tests seed parent templates via the adapter's
    `register(...)` helper.

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

    `capability_lookup`: cross-BC port consumed by Equipment BC's
    `get_asset_integration_view` handler to fetch the set of
    Recipe Capabilities whose `required_affordances` are covered
    by an Asset's combined Family affordances. Recipe BC ships
    `PostgresCapabilityLookup` as the production adapter (reads
    `proj_recipe_capability_summary`). Test environments default
    to `AlwaysEmptyCapabilityLookup` (returns `[]`) so existing
    Equipment tests do not have to seed Capability projection
    rows; surface-specific tests override with a fake that returns
    seeded references or with the real adapter explicitly. The
    port preserves Family's vocabulary discipline ("Capability"
    stays a Recipe word) by isolating the Recipe reference type
    behind a Protocol the handler maps onto the local
    `CapabilityView` response shape.

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

    `spend_guard`: the pre-call half of budget enforcement, consulted by
    the steering brain before each LLM call; see the field docstring.

    `spend_lookup`: cross-BC port consumed by the budget gate at the
    LLM subscribers' seams (RunDebriefer / CautionDrafter) to sum an
    agent's recorded spend in a cap window before permitting the next
    call. Planned consumers, not wired today: the regenerate slice and
    the Operation BC steering brain at the per-call pre-estimate tier.
    Decision BC ships `PostgresSpendLookup` as the production adapter
    (sums `entries_decision_inferences`). Test environments default
    to `AlwaysZeroSpendLookup` (nothing spent) so a declared cap
    never blocks tests that don't exercise budget gating.

    `language_model_lookup`: cross-cutting port consumed by Agent BC's
    `define_agent` handler to gate agent registration on the target
    model identity holding an Approved catalog entry (the shipped
    fleet's defaults are pinned against the seeds by a unit
    consistency test, not by any startup check). Agent BC ships
    `PostgresLanguageModelLookup` as the production adapter (reads
    `proj_agent_language_model_summary`).
    Defaults to `AlwaysApprovedLanguageModelLookup` (every identity
    Approved) so tests and catalog-less deployments keep the
    pre-catalog behavior; standing up a real catalog is what arms the
    gate. Mirrors the `spend_lookup` opt-in posture.

    `model_usage_lookup`: cross-BC port consumed by Agent BC's
    `list_at_risk_results` read slice to enumerate the Decisions whose
    recorded LLM calls touched a catalog entry's model identity (the
    at-risk-results surface a vendor retirement announcement lights
    up). Decision BC ships `PostgresModelUsageLookup` as the production
    adapter (reads `entries_decision_inferences`, the same durable fact
    `spend_lookup` sums). Test environments default to
    `AlwaysEmptyModelUsageLookup` (no recorded call touched any model) so
    tests that don't exercise the at-risk surface stay inert;
    slice-specific tests inject a fake returning seeded rows or the
    real adapter.

    `run_actor_involvement_lookup`: cross-BC port consumed by the
    authority-revocation holder subscriber (K3) to resolve the
    in-flight Runs a revoked principal drives and hold each. Run BC
    ships `PostgresRunActorInvolvementLookup` as the production adapter
    (reads `proj_run_actor_involvement`). Test environments default to
    `NoInvolvementLookup` (returns `[]`) so existing tests don't have
    to seed runs; kill-switch tests override with the real adapter.
    Mirrors the `ClearanceLookup` / `CautionLookup` test-default pattern.

    `consequence_lookup`: cross-BC port consumed by Run BC's `stop_run`
    handler for the consequence gate (Gate IV): is this action covered
    by a GRANTED Ratification (a second, independent principal's
    co-signature)? Trust BC ships `PostgresConsequenceLookup` as the
    production adapter (reads `proj_trust_ratification_coverage`). Test
    environments default to `AlwaysRatifiedConsequenceLookup` (coverage
    always present) so existing stop_run tests stay green with stop_run
    in the ratification allowlist; consequence-gate tests override with
    `NeverRatifiedConsequenceLookup` (refuse-and-hold path) or the real
    adapter (end-to-end).

    `dataset_distribution_lookup`: cross-BC port consumed by Run BC's
    `start_run` handler to gate a reconstruction Run on each declared
    input Dataset (`StartRun.input_dataset_ids`) having a Verified
    Distribution (genesis-only). Data BC ships
    `PostgresDatasetDistributionLookup` as the production adapter (reads
    `proj_data_distribution_summary`, excludes Discarded rows). Test
    environments default to `NoDatasetDistributionsLookup` (every Dataset
    has no Distribution), the conservative default: a Run that declares an
    input but seeds nothing fails the gate. Gate-specific tests override
    with `SeededDatasetDistributionLookup`. Ordinary acquisition Runs
    declare no inputs, so the handler skips the lookup and the gate is
    dormant. See [[project_run_input_dependency_design]].

    `compute_reachability_lookup`: cross-BC-style port consumed by Run BC's
    `start_run` handler to resolve `StartRun.compute_resource_code` to the
    set of Storage Supply ids the named compute resource can read, so the
    decider can require each declared input's Verified Distribution to sit on
    a reachable tier. The production adapter (a deployment-config map resolved
    by Supply name) is deferred; test environments default to
    `NoComputeReachabilityLookup` (every code unknown), the conservative
    default: a Run naming a compute resource fails with
    `RunComputeResourceUnknownError` unless the test seeds a mapping with
    `SeededComputeReachabilityLookup`. A Run naming no compute resource never
    calls the lookup, so the reachability arm stays dormant.

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

    `facility_lookup`: cross-aggregate port consumed by Federation BC's
    `register_facility` handler to validate parent.kind=Site at
    cross-stream boundary (per [[project-slice6-design]] L2; closes the
    Slice 5 deferral). Future Slice 6 Sub-Slice B consumers
    (`add_facility_trust_anchor_credential` decider) will also consume
    this port. Federation BC ships `PostgresFacilityLookup` as the
    production adapter (reads `proj_federation_facility_summary` shipped
    Slice 5 Sub-Slice B, keyed by `facility_id`). Test environments
    default to `InMemoryFacilityLookup`; register_facility handler /
    decider tests seed facilities explicitly via the adapter's
    `register(...)` helper. Mirrors the credential_lookup pattern: the
    handler does the async lookup and threads the result through to the
    decider as the slice's parent-lookup parameter, keeping the decider
    pure.

    `asset_lookup`: cross-aggregate port consumed by cross-BC
    consumers that hold an `AssetId` from the wire and need to
    validate the Asset exists before committing a command. First
    consumer is Supply BC's `register_supply` handler (Session 5
    Slice 7B): it resolves `command.containing_asset_id` to an
    `AssetLookupResult` and threads the result into the decider.
    Future Slice 8 (Asset.facility_id back-binding) and potential
    Safety / Caution BC consumers will also consume this port.
    Equipment BC ships `PostgresAssetLookup` as the production
    adapter (reads `proj_equipment_asset_summary` shipped Phase
    8e-3a). Test environments default to `InMemoryAssetLookup`;
    cross-BC binding tests seed assets via the adapter's
    `register(...)` helper.

    `family_lookup`: cross-aggregate port consumed by Layer-3 sub-slice
    3D's `bind_plan_role` handler (per
    [[project-role-aggregate-design]] Lock 17). Walks
    Asset.family_ids -> FamilyLookup.lookup -> presents_as ∩
    affordance-superset using the ANY-single-family disjunction
    semantic. Equipment BC ships `PostgresFamilyLookup` as the
    production adapter (reads `proj_equipment_family_summary` with
    the Layer-3 sub-slice 3B presents_as + affordances columns).
    Test environments default to `InMemoryFamilyLookup`; 3D consumer
    tests seed Families via the adapter's `register(...)` helper.

    `assembly_lookup`: cross-aggregate port consumed by 3D's
    `bind_plan_role` handler for the Assembly satisfaction branch.
    When the candidate Asset carries `fixture_id`, the handler
    loads the Fixture, then `AssemblyLookup.lookup(fixture.assembly_id)`,
    and the decider ORs-in `role_kind in assembly.presents_as` on
    top of the Family disjunction (closes the Microscope-Assembly
    worked example from the design memo). Equipment BC ships
    `PostgresAssemblyLookup` as the production adapter (reads
    `proj_equipment_assembly_summary` with the 3C presents_as
    column). Test environments default to `InMemoryAssemblyLookup`.

    `role_lookup`: cross-aggregate port consumed by Layer-3 sub-slices
    of [[project-role-aggregate-design]]. 3B `add_family_presents_as`
    decider validates role_id resolves AND that the Family's
    Affordances superset Role.required_affordances. 3C
    `add_assembly_presents_as` decider validates role_id resolves
    (affordance-superset deferred to register_fixture layer). 3D
    `bind_plan_role` handler walks Asset.family_ids ->
    a gather of FamilyLookup.lookup (one per family) -> RoleLookup.lookup
    for the role_kind satisfaction path (Lock 17 ANY-single-family
    disjunction). 3E
    `update_capability_suggested_roles` handler validates every
    proposed RoleId resolves (Lock 10 documentation-only event).
    Equipment BC ships `PostgresRoleLookup` as the production adapter
    (reads `proj_equipment_role_summary` shipped Layer-3 sub-slice
    3A). Test environments default to `InMemoryRoleLookup`; consumer
    tests seed Roles via the adapter's `register(...)` helper or
    leave the registry empty for the missing-role path.

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
    clearance_template_lookup: ClearanceTemplateLookup
    caution_lookup: CautionLookup
    capability_lookup: CapabilityLookup
    supply_lookup: SupplyLookup
    run_actor_involvement_lookup: RunActorInvolvementLookup
    consequence_lookup: ConsequenceLookup
    dataset_distribution_lookup: DatasetDistributionLookup
    compute_reachability_lookup: ComputeReachabilityLookup
    credential_lookup: CredentialLookup
    facility_lookup: FacilityLookup
    asset_lookup: AssetLookup
    family_lookup: FamilyLookup
    assembly_lookup: AssemblyLookup
    role_lookup: RoleLookup
    enclosure_lookup: EnclosureLookup
    spend_lookup: SpendLookup
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
    beam_availability_lookup: BeamAvailabilityLookup = field(default_factory=AllBeamOpenLookup)
    """Cross-BC port consumed by Run BC's `start_run` and Operation
    BC's `start_procedure` to read live beam-availability state (the
    front-end + station `BeamBlockingM` shutters and the ACIS FES-permit
    composite) at the start instant and gate the start (BEAM-1).

    UNIQUE among the cross-BC lookups in carrying a default: every other
    lookup reads a projection and is built at Kernel-construction time,
    but the production beam adapter (`ControlPortBeamAvailabilityLookup`)
    reads LIVE through the Operation BC's `ControlPort`, which is not on
    the Kernel and is only materialised during wiring. So the Kernel
    defaults to the always-open `AllBeamOpenLookup` stub (preserving the
    pre-BEAM-1 no-gate behavior + the test default) and the composition
    root overrides it post-construction via `dataclasses.replace` with a
    `ControlPortBeamAvailabilityLookup` over the shared ControlPort when
    `BEAM_AVAILABILITY_PVS` is configured. Gate-specific tests likewise
    `replace` it with a stub returning the reading under test."""
    spend_guard: SpendGuard = field(default_factory=AlwaysGrantedSpendGuard)
    """Pre-call budget permission for an agent's next LLM call (the
    per-call pre-estimate enforcement tier). Defaults to the always-pass
    stub so tests and non-steering deployments are unaffected; the
    composition root binds the Agent BC's `BudgetSpendGuard` in
    production, which reads the caller's declared caps and the recorded
    spend the `spend_lookup` sums."""

    inference_recorder: InferenceRecorder = field(default_factory=NullInferenceRecorder)
    """Cross-BC capability port the LLM-backed agents call to record one
    model-provenance trace (provider, resolved model snapshot, token usage)
    per Decision into the Decision BC's Inference logbook.

    A capability PORT, NOT the Decision BC's `InferenceStore` (which stays
    BC-internal in `wire_decision` per the store-stays-BC-internal rule above):
    the producers cannot reach that store or import the sibling BC's
    `append_inferences` handler across the BC boundary. Defaults to the no-op
    `NullInferenceRecorder` so unwired kernels and unit tests stay inert; the
    composition root overrides it post-construction via `dataclasses.replace`
    with an implementor that delegates to the `append_inferences` handler once
    the Decision handlers are wired (mirrors the `beam_availability_lookup`
    post-construction override)."""

    language_model_lookup: LanguageModelLookup = field(
        default_factory=AlwaysApprovedLanguageModelLookup
    )
    """Resolve a model identity (provider + model) to its catalog entry.
    Defaults to the always-approved stub so tests and deployments without
    a catalog keep the pre-catalog `define_agent` behavior; the
    composition root binds the Agent BC's `PostgresLanguageModelLookup`
    over `proj_agent_language_model_summary` when a pool exists, arming
    the Approved-entry gate."""

    model_usage_lookup: ModelUsageLookup = field(default_factory=AlwaysEmptyModelUsageLookup)
    """Enumerate the Decisions whose recorded LLM calls touched one
    model identity (one row per Decision, newest touching call).
    Defaults to the always-empty stub so tests and deployments without
    an inference logbook see an empty at-risk list; the composition
    root binds the Decision BC's `PostgresModelUsageLookup` over
    `entries_decision_inferences` when a pool exists."""

    allocation_lookup: AllocationLookup = field(default_factory=NoActiveAllocationLookup)
    """Resolve the deployment's single Active spending envelope.
    Consumed by the envelope arm of the budget gate stack (post-hoc
    subscriber gate, pre-estimate `BudgetSpendGuard`) and by the
    budget BC's CampaignClosed sealer. Defaults to the never-Active
    stub so tests and deployments without a declared allocation keep
    the unconstrained behavior; the composition root binds the budget
    BC's `PostgresAllocationLookup` over
    `proj_budget_allocation_summary` when a pool exists. Activating
    an envelope is what arms the check (the `spend_lookup` opt-in
    posture)."""


Teardown = Callable[[], Awaitable[None]]
"""Async callable returned by kernel-construction; the FastAPI
lifespan calls this to release pool resources at shutdown."""


__all__ = [
    "Kernel",
    "Teardown",
]
