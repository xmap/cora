"""Enclosure permit gates Run.start at APS 2-BM.

cluster: Staging
archetype: gate
bc_primary: Enclosure
bc_touches: Enclosure, Run, Recipe, Equipment, Subject

Pins the full composition for the Sub-Slice F payoff:
  - Seed the full Run upstream chain (Family + Asset + Method +
    Practice + Plan + Subject) against real Postgres event store.
  - Register an Enclosure whose `containing_asset_id` matches the
    Plan's bound Asset, then drain the projection so
    `proj_enclosure_summary` carries the row.
  - First start_run is REFUSED (`RunRequiresPermittedEnclosureError`)
    because the genesis row is `permit_status=Unknown`.
  - Walk the Enclosure to `Permitted` via `observe_enclosure_status`,
    drain again, retry: start_run SUCCEEDS.
  - Walk the Enclosure back to `NotPermitted`, drain, retry:
    start_run is REFUSED again.

Closes the EXEMPT_FROM_INTEGRATION gap for
`cora.enclosure.features.register_enclosure`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosurePermitStatus,
    MonitorRef,
)
from cora.enclosure.features import observe_enclosure_status, register_enclosure
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import (
    RunEnclosureCoverageMismatchError,
    RunRequiresPermittedEnclosureError,
)
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.shared.identity import MonitorSourceId
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_T0 = datetime(2026, 6, 9, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 9, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000f001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000f002")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d6f1")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000f003"))


async def _drain_enclosure(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_upstream_chain(
    db_pool: asyncpg.Pool,
) -> tuple[Kernel, UUID, UUID, UUID]:
    """Build the Family + Asset + Method + Practice + Plan + Subject chain
    a Run requires. Returns (deps, plan_id, subject_id, asset_id) so the
    test can seed an Enclosure binding against asset_id.
    """
    asset_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()
    queue = [
        uuid4(),  # cap_id
        uuid4(),  # cap event
        asset_id,
        uuid4(),  # asset register event
        uuid4(),  # asset addfamily event
        uuid4(),  # method_id
        uuid4(),  # method event
        uuid4(),  # practice_id
        uuid4(),  # practice event
        plan_id,
        uuid4(),  # plan event
        subject_id,
        uuid4(),  # subject register event
        uuid4(),  # subject mount event
        uuid4(),  # run_id
        uuid4(),  # run event
        *[uuid4() for _ in range(10)],
    ]
    deps = build_postgres_deps(db_pool, now=_T0, ids=queue)
    # Replace the default AlwaysPermittedEnclosureLookup with the real
    # Postgres adapter so the gate fires against the real
    # proj_enclosure_summary projection (cross-BC end-to-end composition).
    deps = dataclasses.replace(deps, enclosure_lookup=PostgresEnclosureLookup(db_pool))

    cap_id = queue[0]
    await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="XRF Fly Scan",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=queue[5], site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="2-BM Pilot Scan",
            practice_id=queue[7],
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_T0, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return deps, plan_id, subject_id, asset_id


async def _seed_enclosure(db_pool: asyncpg.Pool, *, asset_id: UUID) -> UUID:
    """Register a new Enclosure whose containing_asset_id matches the
    Run's bound Asset, then drain the projection."""
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(3)])
    suffix = uuid4().hex[:8]
    eid = await register_enclosure.bind(deps)(
        RegisterEnclosure(name=f"2-BM-A-hutch-{suffix}", containing_asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_enclosure(db_pool)
    return eid


async def _observe(
    db_pool: asyncpg.Pool,
    *,
    enclosure_id: UUID,
    new_status: EnclosurePermitStatus,
    now: datetime,
) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[uuid4() for _ in range(3)])
    await observe_enclosure_status.bind(deps)(
        ObserveEnclosureStatus(
            enclosure_id=EnclosureId(enclosure_id),
            new_status=new_status,
            reason="interlock walkdown",
            monitor_source_id=_MONITOR_SOURCE_ID,
            monitor_ref=MonitorRef(source_kind="EpicsPv", source_id="2bm:hutch:permit"),
            trigger="Monitor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_enclosure(db_pool)


@pytest.mark.integration
async def test_2bm_enclosure_preflight_walks_unknown_to_permitted_to_notpermitted(
    db_pool: asyncpg.Pool,
) -> None:
    """Full lifecycle exercise of the Sub-Slice F gate via real Postgres.

    Step 1: register Enclosure -> permit_status="Unknown" by default.
    Step 2: start_run is REFUSED (RunRequiresPermittedEnclosureError).
    Step 3: walk Enclosure to "Permitted" via observe_enclosure_status.
    Step 4: start_run SUCCEEDS.
    Step 5: walk Enclosure to "NotPermitted".
    Step 6: start_run is REFUSED again.
    """
    deps, plan_id, subject_id, asset_id = await _seed_upstream_chain(db_pool)
    enclosure_id = await _seed_enclosure(db_pool, asset_id=asset_id)

    # Step 2: Unknown permit_status -> gate fails.
    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        await start_run.bind(deps)(
            StartRun(name="Refused on Unknown", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    failing = exc_info.value.enclosure_status_summary
    assert any(eid == enclosure_id for eid, _ in failing)

    # Step 3: walk to Permitted.
    await _observe(
        db_pool,
        enclosure_id=enclosure_id,
        new_status=EnclosurePermitStatus.PERMITTED,
        now=_T1,
    )

    # Step 4: gate passes.
    returned_id = await start_run.bind(deps)(
        StartRun(name="Allowed when Permitted", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id is not None

    # Step 5+6: walk back to NotPermitted. A second start_run against
    # the same plan would emit a fresh run_id (new aggregate), so the
    # gate must fire on the new attempt.
    await _observe(
        db_pool,
        enclosure_id=enclosure_id,
        new_status=EnclosurePermitStatus.NOT_PERMITTED,
        now=_T2,
    )
    with pytest.raises(RunRequiresPermittedEnclosureError):
        await start_run.bind(deps)(
            StartRun(name="Refused on NotPermitted", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_2bm_enclosure_preflight_raises_coverage_mismatch_on_mixed_bindings(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Enclosures bind the same Asset; one is Permitted, the other
    Unknown. The pre-flight gate fires CoverageMismatch (not Requires)
    because the binding set is mixed: at least one row passes and at
    least one row fails the Permitted-and-Active check.

    End-to-end against real Postgres exercises the wire + projection +
    Postgres lookup adapter + decider classification path. Mirrors the
    contract-tier mixed-status test but uses the production adapter
    so projection-side bugs (e.g. UNIQUE INDEX swallowing one row,
    SELECT filter dropping NotPermitted) would surface here first.
    """
    deps, plan_id, subject_id, asset_id = await _seed_upstream_chain(db_pool)
    permitted_enclosure_id = await _seed_enclosure(db_pool, asset_id=asset_id)
    unknown_enclosure_id = await _seed_enclosure(db_pool, asset_id=asset_id)

    await _observe(
        db_pool,
        enclosure_id=permitted_enclosure_id,
        new_status=EnclosurePermitStatus.PERMITTED,
        now=_T1,
    )

    with pytest.raises(RunEnclosureCoverageMismatchError) as exc_info:
        await start_run.bind(deps)(
            StartRun(name="Mixed bindings", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    failing = exc_info.value.enclosure_status_summary
    enclosure_ids = {eid for eid, _ in failing}
    assert unknown_enclosure_id in enclosure_ids
    assert permitted_enclosure_id not in enclosure_ids
