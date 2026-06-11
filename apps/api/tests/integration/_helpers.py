"""Shared test helpers for integration tests against real Postgres.

Mirrors `tests/unit/_helpers.py::build_deps` but constructs a Kernel
backed by `PostgresEventStore` + `PostgresIdempotencyStore` over the
testcontainers `db_pool` fixture from `tests/integration/conftest.py`.

## Usage

```python
from tests.integration._helpers import build_postgres_deps

deps = build_postgres_deps(db_pool, ids=[method_id, event_id], now=_NOW)
deps = build_postgres_deps(db_pool, ids=[...], now=_NOW, authz=RecordingAuthorize())
```

## Why a separate factory from the unit helper

Integration tests need PostgresEventStore + PostgresIdempotencyStore
constructed from the per-test `db_pool` fixture; unit tests use the
in-memory adapters with no pool. The two flows can't share a single
factory without either (a) optional pool with conditional adapter
selection (silently surprising) or (b) cross-tier imports (couples
test tiers).

`now` is required (no DEFAULT_NOW analog): integration tests pin a
per-test timestamp so the persisted event's `occurred_at` traces
back to the test that wrote it.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.adapters.postgres_profile_store import PostgresProfileStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_postgres_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    LLM,
    AllowAllAuthorize,
    AlwaysCoveredClearanceLookup,
    AlwaysQuietCautionLookup,
    AssetLookup,
    Authorize,
    CautionLookup,
    ClearanceLookup,
    CredentialLookup,
    EventStore,
    FacilityLookup,
    FakeClock,
    FixedIdGenerator,
    IdempotencyStore,
    ProfileStore,
)
from cora.shared.facility_code import FacilityCode

_DEFAULT_SELF_FACILITY_CODE = "cora"
"""Matches the default `Settings.self_facility_code` so register_supply
+ future cross-BC Facility-binding integration tests resolve
`facility_code="cora"` without each test having to seed it explicitly.
Tests that need a different slug pass `facility_lookup=` with their
own seed map."""

_DEFAULT_SELF_FACILITY_ID = UUID("01900000-0000-7000-8000-00000000c07a")


def build_postgres_deps(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    ids: list[UUID] | None = None,
    authz: Authorize | None = None,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
    clearance_lookup: ClearanceLookup | None = None,
    caution_lookup: CautionLookup | None = None,
    credential_lookup: CredentialLookup | None = None,
    facility_lookup: FacilityLookup | None = None,
    asset_lookup: AssetLookup | None = None,
    profile_store: ProfileStore | None = None,
    llm: LLM | None = None,
) -> Kernel:
    """Build a Kernel for integration-test handler invocation against real Postgres.

    Defaults: AllowAllAuthorize, fresh PostgresEventStore(pool), fresh
    PostgresIdempotencyStore(pool), `AlwaysCoveredClearanceLookup` (the
    safety-gate bypass stub), `AlwaysQuietCautionLookup` (the caution-
    snapshot quiet stub). Pass `event_store=` / `idempotency_store=` /
    `clearance_lookup=` / `caution_lookup=` to share an already-
    constructed adapter or to exercise a specific behavior (for example,
    gate tests pass `PostgresClearanceLookup(pool)` and seed a real
    clearance; snapshot tests pass `PostgresCautionLookup(pool)` and
    seed a real caution via `register_caution`).

    `ids=` queues UUIDs for the FixedIdGenerator (handler consumes them
    in order: aggregate ids first, then event ids per emitted event).
    """
    if facility_lookup is None:
        seeded = InMemoryFacilityLookup()
        seeded.register(
            facility_id=_DEFAULT_SELF_FACILITY_ID,
            code=FacilityCode(_DEFAULT_SELF_FACILITY_CODE),
            kind="Site",
            status="Active",
        )
        facility_lookup = seeded
    return make_postgres_kernel(
        pool,
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FakeClock(now),
        id_generator=FixedIdGenerator(list(ids or [])),
        authz=authz or AllowAllAuthorize(),
        event_store=event_store,
        idempotency_store=idempotency_store,
        clearance_lookup=clearance_lookup or AlwaysCoveredClearanceLookup(),
        caution_lookup=caution_lookup or AlwaysQuietCautionLookup(),
        credential_lookup=credential_lookup,
        facility_lookup=facility_lookup,
        asset_lookup=asset_lookup,
        profile_store=profile_store,
        llm=llm,
    )


_DEFAULT_SEED_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DEFAULT_SEED_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


async def seed_capability_postgres(
    event_store: EventStore,
    capability_id: UUID,
    *,
    code: str = "cora.capability.test",
    name: str = "TestCapability",
    shapes: object | None = None,
    now: datetime | None = None,
    correlation_id: UUID = _DEFAULT_SEED_CORRELATION_ID,
    principal_id: UUID = _DEFAULT_SEED_PRINCIPAL_ID,
) -> None:
    """Seed a Capability stream against a Postgres event store.

    Mirrors `tests.unit._helpers.seed_capability`
    but threads the Postgres event store explicitly. Used by integration
    tests that call `DefineMethod(...)` or `RegisterProcedure(...)` —
    the bound Capability stream must exist before the handler runs
    (eventual-consistency: handler raises `CapabilityNotFoundError`
    when the stream is missing). Defaults to both METHOD + PROCEDURE
    executor shapes so the same seed serves both binding paths.
    """
    import contextlib
    from uuid import uuid4 as _uuid4

    from cora.infrastructure.event_envelope import to_new_event as _to_new_event
    from cora.infrastructure.ports.event_store import ConcurrencyError
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

    occurred_at = now or datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
    shapes_set: frozenset[ExecutorShape] = shapes or frozenset(  # type: ignore[assignment]
        {ExecutorShape.METHOD, ExecutorShape.PROCEDURE}
    )
    event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode(code).value,
        name=CapabilityName(name).value,
        required_affordances=frozenset(),
        executor_shapes=shapes_set,
        occurred_at=occurred_at,
    )
    # Idempotent seed: another test in the same PG db_pool may have
    # already seeded this capability_id; tolerated via contextlib.suppress
    # so test modules sharing a `_CAPABILITY_ID` constant can call
    # seed_capability_postgres freely from each test without coordinating.
    with contextlib.suppress(ConcurrencyError):
        await event_store.append(
            stream_type="Capability",
            stream_id=capability_id,
            expected_version=0,
            events=[
                _to_new_event(
                    event_type=capability_event_type_name(event),
                    payload=capability_to_payload(event),
                    occurred_at=occurred_at,
                    event_id=_uuid4(),
                    command_name="DefineCapability",
                    correlation_id=correlation_id,
                    principal_id=principal_id,
                )
            ],
        )


_DEFAULT_RUN_CHAIN_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d9ea")


async def seed_run_upstream_chain_postgres(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    method_schema: dict[str, Any] | None = None,
    plan_defaults: dict[str, Any] | None = None,
    capability_id: UUID = _DEFAULT_RUN_CHAIN_CAPABILITY_ID,
    correlation_id: UUID = _DEFAULT_SEED_CORRELATION_ID,
    principal_id: UUID = _DEFAULT_SEED_PRINCIPAL_ID,
) -> tuple[UUID, UUID]:
    """Seed the full upstream chain a Run needs against real Postgres.

    Composition: Family + Capability + Method (optional schema) + Practice +
    Asset (with Family) + Plan (optional defaults) + Subject (Mounted).
    Returns `(plan_id, subject_id)` — the two ids `StartRun` needs.

    Hoisted from `test_run_parameters_handler_postgres.py` once a second
    integration test (12b `pinned_calibration_ids`) needed the same scaffold;
    avoids the private-import + `# pyright: ignore` smell of cross-test
    imports. The function uses fresh UUIDs (uuid4) on every call so
    multiple test fns can call it in the same db_pool without colliding
    on stream ids.

    `method_schema`: optional JSON Schema dict passed to
    `update_method_parameters_schema` — STRICT validation at Run start
    requires this to be set for any test that supplies non-empty
    `override_parameters` or `plan_defaults`. Pass `None` for the
    parameter-less Run path (12b `pinned_calibration_ids` tests).

    `plan_defaults`: optional dict patched into the Plan's
    `default_parameters` via `update_plan_default_parameters`. Pass
    `None` to leave defaults empty.
    """
    from uuid import uuid4

    from cora.equipment.aggregates.asset import AssetTier
    from cora.equipment.features import (
        add_asset_family,
        define_family,
        register_asset,
    )
    from cora.equipment.features.add_asset_family import AddAssetFamily
    from cora.equipment.features.define_family import DefineFamily
    from cora.equipment.features.register_asset import RegisterAsset
    from cora.recipe.features import (
        define_method,
        define_plan,
        define_practice,
        update_method_parameters_schema,
        update_plan_default_parameters,
    )
    from cora.recipe.features.define_method import DefineMethod
    from cora.recipe.features.define_plan import DefinePlan
    from cora.recipe.features.define_practice import DefinePractice
    from cora.recipe.features.update_method_parameters_schema import (
        UpdateMethodParametersSchema,
    )
    from cora.recipe.features.update_plan_default_parameters import (
        UpdatePlanDefaultParameters,
    )
    from cora.subject.features import mount_subject, register_subject
    from cora.subject.features.mount_subject import MountSubject
    from cora.subject.features.register_subject import RegisterSubject
    from tests.unit.subject._helpers import seed_active_asset

    # Generate enough event ids for every step in the chain.
    ids = [uuid4() for _ in range(40)]
    deps = build_postgres_deps(pool, now=now, ids=ids)

    family_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await seed_capability_postgres(deps.event_store, capability_id, now=now)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=capability_id,
            name="Test Method",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    if method_schema is not None:
        await update_method_parameters_schema.bind(deps)(
            UpdateMethodParametersSchema(method_id=method_id, parameters_schema=method_schema),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
    site_id = uuid4()
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=site_id),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="TestAsset", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    if plan_defaults:
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch=plan_defaults),
            principal_id=principal_id,
            correlation_id=correlation_id,
        )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=now, correlation_id=correlation_id
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason="test"),
        principal_id=principal_id,
        correlation_id=correlation_id,
    )

    return plan_id, subject_id


def make_pg_profile_store(pool: asyncpg.Pool) -> ProfileStore:
    """Fresh `PostgresProfileStore` for integration-test handler invocation.

    Mirrors `tests.unit._helpers.make_profile_store` but builds the
    real adapter over the testcontainers `db_pool`. Use this for
    `register_actor.bind`, `get_actor.bind`, `define_agent.bind`
    invocations in integration tests so writes land in the actual
    `actor_profile` table (the same one production reads).
    """
    return PostgresProfileStore(pool)


__all__ = [
    "build_postgres_deps",
    "make_pg_profile_store",
    "seed_capability_postgres",
    "seed_run_upstream_chain_postgres",
]
