"""Shared test helpers for unit-test handlers.

Per the Phase-8e-1c Option-4 audit + `memory/project_deferred.md`
"Test helper consolidation" entry: every BC's command/query handler
test file historically defined its own `_build_deps` function with a
near-identical body (54 instances pre-consolidation). This module
provides the canonical factory; per-BC tests migrate opportunistically
when Option 1 (spread the projection pattern) touches that BC.

## Usage

```python
from tests.unit._helpers import DEFAULT_NOW, DenyAllAuthorize, build_deps

deps = build_deps(ids=[_NEW_ID, _EVENT_ID])
deps = build_deps(ids=[...], deny=True)              # auth-deny path
deps = build_deps(ids=[...], event_store=preseeded)  # pre-seeded store
deps = build_deps(ids=[...], now=custom_clock_time)  # custom clock
```

## Design notes

- `build_deps` is a function (not a pytest fixture) so test files can
  call it from helper functions, parametrize over it, and mix it with
  module-level constants without dependency-injection ceremony.
- `DenyAllAuthorize` returns the generic reason `"denied for test"`.
  Tests asserting BC-specific deny reasons should construct their own
  Deny stub locally.
- `DEFAULT_NOW` is May 12, 2026 14:00 UTC — the canonical test clock
  used across the suite. Tests that need a specific timestamp pass
  `now=` explicitly.
- Pool stays None (in-memory test environment); Postgres-backed tests
  live in `tests/integration/` and build their own Kernel against the
  testcontainers pool.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.adapters.in_memory_profile_store import InMemoryProfileStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    LLM,
    Allow,
    AllowAllAuthorize,
    AssemblyLookup,
    AssetLookup,
    Authorize,
    AuthzResult,
    CredentialLookup,
    Deny,
    EventStore,
    FacilityLookup,
    FakeClock,
    FamilyLookup,
    FixedIdGenerator,
    ProfileStore,
    RoleLookup,
)
from cora.recipe.aggregates.capability import (
    CapabilityCode,
    CapabilityDefined,
    CapabilityName,
    ExecutorShape,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import (
    to_payload as capability_to_payload,
)
from cora.shared.facility_code import FacilityCode

DEFAULT_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
"""Canonical test clock used across unit tests. Tests that need a
specific timestamp pass `now=` explicitly to `build_deps`."""


class DenyAllAuthorize:
    """Test stub that denies every authorize call with the generic
    reason `"denied for test"`. Tests asserting BC-specific deny
    reasons should construct their own Deny stub locally."""

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = UUID(int=0),  # noqa: B008
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


class RecordingAuthorize:
    """Authorize stub that records every call so tests can assert the
    shape (principal_id, command_name, conduit_id, surface_id) the
    handler invokes the port with. Returns Allow on every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, UUID, UUID]] = []

    async def authorize(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = UUID(int=0),  # noqa: B008
    ) -> AuthzResult:
        self.calls.append((principal_id, command_name, conduit_id, surface_id))
        return Allow()


def build_deps(
    *,
    ids: list[UUID] | None = None,
    now: datetime | None = None,
    event_store: EventStore | None = None,
    trust_policy_id: UUID | None = None,
    deny: bool = False,
    authz: Authorize | None = None,
    llm: LLM | None = None,
    profile_store: ProfileStore | None = None,
    credential_lookup: CredentialLookup | None = None,
    facility_lookup: FacilityLookup | None = None,
    asset_lookup: AssetLookup | None = None,
    family_lookup: FamilyLookup | None = None,
    assembly_lookup: AssemblyLookup | None = None,
    role_lookup: RoleLookup | None = None,
) -> Kernel:
    """Build a Kernel for unit-test handler invocation.

    Defaults: FakeClock at DEFAULT_NOW, AllowAllAuthorize, fresh
    InMemoryEventStore, fresh InMemoryIdempotencyStore, fresh
    InMemoryProfileStore, no pool. Pass `ids=` for the
    FixedIdGenerator queue (the handler consumes them in order:
    aggregate ids first, then event ids per emitted event).

    `authz` overrides the default authorize port (use this for
    tests injecting a recording / counting / specific-reason
    Authorize stub). When `authz` is set, `deny` is ignored.

    `trust_policy_id` sets `Settings.trust_policy_id` (default None =
    AllowAll posture). Use this for tests that exercise startup checks
    keyed on whether real authz is configured.

    `llm` wires a test LLM (typically
    `FakeLLM`) when the handler under test consumes one
    (eg. `regenerate_run_debrief`). Defaults to None so the vast majority
    of tests that don't need an LLM stay LLM-free.

    `profile_store` injects a pre-built PII vault adapter (typically
    when a test wants to seed the vault before invoking the handler,
    or wants to assert on the vault state afterwards via the same
    instance). Defaults to a fresh `InMemoryProfileStore` per call.

    `credential_lookup` injects a pre-built `CredentialLookup` adapter
    (typically `InMemoryCredentialLookup` seeded with one or more
    credential summaries) so Seal handler tests can pre-register the
    refs the slice will resolve before invoking the decider. Defaults
    to a fresh empty `InMemoryCredentialLookup` per call.

    `facility_lookup` injects a pre-built `FacilityLookup` adapter
    (typically `InMemoryFacilityLookup` seeded with one or more
    facility summaries) so `register_facility`-with-parent tests can
    pre-register the parent Facility before invoking the decider.
    Defaults to a fresh empty `InMemoryFacilityLookup` per call.

    `asset_lookup` injects a pre-built `AssetLookup` adapter
    (typically `InMemoryAssetLookup` seeded with one or more Asset
    summaries) so cross-BC binding tests (Slice 7B Supply
    `containing_asset_id` resolution, future Slice 8 Asset
    `facility_id` binding) can pre-register the target Asset before
    invoking the decider. Defaults to a fresh empty
    `InMemoryAssetLookup` per call; tests that don't bind to an
    Asset never touch it.

    `family_lookup` / `assembly_lookup` / `role_lookup` inject
    pre-built Equipment-BC cross-aggregate adapters so Layer-3
    `bind_plan_role` (role_kind path) + `update_capability_suggested_roles`
    handler tests can pre-register the Roles / Families / Assemblies
    the slice resolves at the handler edge. Each defaults to a fresh
    empty in-memory adapter per call; tests on the slice-1 family_id
    path never touch them.
    """
    if authz is None:
        authz = DenyAllAuthorize() if deny else AllowAllAuthorize()
    # Default a seeded self-Facility ("cora") into the FacilityLookup so
    # tests exercising register_supply / future cross-BC Facility binding
    # resolve `facility_code="cora"` without each test having to wire it
    # explicitly. Tests that need a different slug pass their own
    # `facility_lookup=` seeded adapter.
    if facility_lookup is None:
        seeded = InMemoryFacilityLookup()
        seeded.register(
            facility_id=UUID("01900000-0000-7000-8000-00000000c07a"),
            code=FacilityCode("cora"),
            kind="Site",
            status="Active",
        )
        facility_lookup = seeded
    # Wire the publish-side InMemory federation adapters by default so
    # tests that exercise wire_calibration (which binds publish_revision)
    # do not hit PublishPortNotWiredError at startup. Tests that want
    # to assert the misconfiguration surface explicitly null them via
    # dataclasses.replace.
    from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup
    from cora.federation.adapters.in_memory_publish_port import InMemoryPublishPort
    from cora.federation.adapters.in_memory_signature_port import InMemorySignaturePort

    return make_inmemory_kernel(
        settings=Settings(app_env="test", trust_policy_id=trust_policy_id),  # type: ignore[call-arg]
        clock=FakeClock(now or DEFAULT_NOW),
        id_generator=FixedIdGenerator(list(ids or [])),
        authz=authz,
        event_store=event_store,
        llm=llm,
        profile_store=profile_store,
        credential_lookup=credential_lookup,
        facility_lookup=facility_lookup,
        asset_lookup=asset_lookup,
        family_lookup=family_lookup,
        assembly_lookup=assembly_lookup,
        role_lookup=role_lookup,
        publish_port=InMemoryPublishPort(),
        signature_port=InMemorySignaturePort(),
        permit_lookup=InMemoryPermitLookup(),
    )


async def seed_capability(
    event_store: EventStore,
    capability_id: UUID,
    *,
    code: str = "cora.capability.test",
    name: str = "TestCapability",
    shapes: frozenset[ExecutorShape] | None = None,
    required_affordances: frozenset[object] | None = None,
    now: datetime | None = None,
) -> None:
    """Seed a Capability stream so `load_capability` returns a real
    Capability state.

    Hoisted to one shared location so every test module that needs
    to seed a Capability before calling `DefineMethod(...)` /
    `RegisterProcedure(...)` uses the same shape. Defaults to
    `ExecutorShape.METHOD` + `ExecutorShape.PROCEDURE` so the same
    seed serves both Method and Procedure binding tests.

    `required_affordances` is `frozenset[Affordance] | None` typed as
    `frozenset[object]` here to avoid Equipment-BC re-import inside
    the helpers module; callers pass `frozenset()` (default) or a
    real frozenset of Affordance values.
    """
    occurred_at = now or DEFAULT_NOW
    shapes_set: frozenset[ExecutorShape] = shapes or frozenset(
        {ExecutorShape.METHOD, ExecutorShape.PROCEDURE}
    )
    # frozenset[object] -> frozenset[Affordance] cast: helper accepts
    # untyped frozensets to avoid an Equipment-BC import in this
    # module; the actual type is enforced by CapabilityDefined's
    # dataclass annotation downstream.
    event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode(code).value,
        name=CapabilityName(name).value,
        required_affordances=required_affordances or frozenset(),  # type: ignore[arg-type]
        executor_shapes=shapes_set,
        occurred_at=occurred_at,
    )
    await event_store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=capability_event_type_name(event),
                payload=capability_to_payload(event),
                occurred_at=occurred_at,
                event_id=uuid4(),
                command_name="DefineCapability",
                correlation_id=UUID("01900000-0000-7000-8000-0000000000aa"),
                principal_id=UUID("01900000-0000-7000-8000-000000000099"),
            )
        ],
    )


def make_profile_store() -> InMemoryProfileStore:
    """Fresh InMemoryProfileStore for unit-test handler invocation.

    Per the PII vault pattern, the Access BC `register_actor` and
    `get_actor` slices plus the Agent BC `define_agent` slice take a
    `ProfileStore` via the `bind(deps, *, profile_store=...)`
    keyword. Tests construct a per-test in-memory store via this
    helper and assert on it directly when they need to (for example
    "register_actor upserts the display name into the vault").
    """
    return InMemoryProfileStore()


__all__ = [
    "DEFAULT_NOW",
    "DenyAllAuthorize",
    "RecordingAuthorize",
    "build_deps",
    "make_profile_store",
    "seed_capability",
]
