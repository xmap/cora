"""Two independent hutch Enclosures gate 2-BM Runs by where the Device sits.

cluster: Staging
archetype: gate
bc_primary: Enclosure
bc_touches: Enclosure, Run, Recipe, Equipment, Subject

APS 2-BM has two experiment stations (hutch A and hutch B) fed from one
beamline. Each hutch is its own access-gated Enclosure with its own
interlock permit, observed independently. A Device physically sits in
exactly one hutch and declares it via `located_in_enclosure_id`; the
pre-flight gate collects the located-in Enclosure of each Plan-bound
Device (and its ancestors) via the chain walk and refuses the Run unless
every collected Enclosure is Permitted-and-Active.

Topology: one 2-BM beamline Unit with two Devices directly under it.
`device_a` is located in Enclosure "2-BM-A"; `device_b` in "2-BM-B".
Three Plans: A-only (binds device_a), B-only (binds device_b), and both
(binds device_a + device_b).

  - test_each_hutch_gates_only_its_own_runs: with hutch A Permitted and
    hutch B NotPermitted, the Plan-A Run starts while the Plan-B Run is
    REFUSED (RunRequiresPermittedEnclosureError). The failing summary
    names enclosure_b, not enclosure_a: each hutch's permit gates only
    the Runs whose Devices sit in it.
  - test_cross_hutch_run_requires_both_hutches_permitted: the Plan-AB
    Run, spanning both hutches while B is still NotPermitted, is REFUSED
    with RunEnclosureCoverageMismatchError (some pass, some fail; the
    summary names the failing enclosure_b). Once hutch B is observed
    Permitted too, the same Plan-AB Run starts.
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
from cora.enclosure.aggregates.enclosure import EnclosurePermitStatus, MonitorRef
from cora.enclosure.features import observe_enclosure_status, register_enclosure
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.equipment.adapters.postgres_asset_lookup import PostgresAssetLookup
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.aggregates.method import ExecutionPattern
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
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_T0 = datetime(2026, 6, 13, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 13, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000a201")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000a202")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0a2f1")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000a203"))
_FACILITY_CODE = "cora"


async def _drain_enclosure(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_enclosure(db_pool: asyncpg.Pool, *, name: str) -> UUID:
    """Register a hutch Enclosure anchored to the seeded `cora` Facility, then
    drain its projection so PostgresEnclosureLookup.find_by_ids resolves it."""
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(3)])
    suffix = uuid4().hex[:8]
    eid = await register_enclosure.bind(deps)(
        RegisterEnclosure(name=f"{name}-{suffix}", facility_code=_FACILITY_CODE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_enclosure(db_pool)
    return eid


async def _observe(
    db_pool: asyncpg.Pool, *, enclosure_id: UUID, new_status: EnclosurePermitStatus, now: datetime
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


async def _seed_two_hutch_topology(
    db_pool: asyncpg.Pool, *, enclosure_a: UUID, enclosure_b: UUID
) -> tuple[Kernel, UUID, UUID, UUID]:
    """Seed a 2-BM Unit + two Devices under it (device_a located in hutch A,
    device_b located in hutch B), and three Plans: A-only, B-only, and both.

    Returns (deps, plan_a_id, plan_b_id, plan_ab_id). The real
    PostgresAssetLookup is wired so start_run's ancestor walk reads each
    Device's located-in pointer from proj_equipment_asset_summary.
    """
    deps, family_id = await _build_deps_and_family(db_pool)

    unit_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="2-BM beamline", tier=AssetTier.UNIT, parent_id=None, facility_code=_FACILITY_CODE
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    device_a_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="HutchA-Detector",
            tier=AssetTier.DEVICE,
            parent_id=unit_id,
            facility_code=None,
            located_in_enclosure_id=enclosure_a,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    device_b_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="HutchB-Detector",
            tier=AssetTier.DEVICE,
            parent_id=unit_id,
            facility_code=None,
            located_in_enclosure_id=enclosure_b,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for device_id in (device_a_id, device_b_id):
        await add_asset_family.bind(deps)(
            AddAssetFamily(asset_id=device_id, family_id=family_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="XRF Fly Scan",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_a_id = await define_plan.bind(deps)(
        DefinePlan(
            name="Hutch-A Scan", practice_id=practice_id, asset_ids=frozenset({device_a_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_b_id = await define_plan.bind(deps)(
        DefinePlan(
            name="Hutch-B Scan", practice_id=practice_id, asset_ids=frozenset({device_b_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_ab_id = await define_plan.bind(deps)(
        DefinePlan(
            name="Cross-Hutch Scan",
            practice_id=practice_id,
            asset_ids=frozenset({device_a_id, device_b_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)
    return deps, plan_a_id, plan_b_id, plan_ab_id


async def _build_deps_and_family(db_pool: asyncpg.Pool) -> tuple[Kernel, UUID]:
    """Build Postgres deps with the real Asset + Enclosure lookups wired, and
    define the shared Family the Devices and Method use. Returns (deps,
    family_id)."""
    deps = build_postgres_deps(
        db_pool,
        now=_T0,
        ids=[uuid4() for _ in range(60)],
        asset_lookup=PostgresAssetLookup(db_pool),
    )
    deps = dataclasses.replace(deps, enclosure_lookup=PostgresEnclosureLookup(db_pool))
    family_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return deps, family_id


async def _start_run_with_fresh_mount(
    deps: Kernel, db_pool: asyncpg.Pool, *, plan_id: UUID, name: str
) -> UUID:
    """Register a Subject, mount it onto a fresh distinct Asset, and start a
    Run against `plan_id`. Each call uses its own mount Asset (asset_id=uuid4)
    so repeated start_run calls in one test do not collide on a single mount.
    """
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name=f"Sample-{uuid4().hex[:8]}"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, asset_id=uuid4(), now=_T0, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return await start_run.bind(deps)(
        StartRun(name=name, plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_each_hutch_gates_only_its_own_runs(db_pool: asyncpg.Pool) -> None:
    """Hutch A Permitted, hutch B NotPermitted: the Plan-A Run starts while
    the Plan-B Run is REFUSED. The failing summary names enclosure_b, never
    enclosure_a -- each hutch's permit gates only the Runs whose Devices sit
    in it."""
    enclosure_a = await _seed_enclosure(db_pool, name="2-BM-A")
    enclosure_b = await _seed_enclosure(db_pool, name="2-BM-B")
    deps, plan_a_id, plan_b_id, _plan_ab_id = await _seed_two_hutch_topology(
        db_pool, enclosure_a=enclosure_a, enclosure_b=enclosure_b
    )

    await _observe(
        db_pool, enclosure_id=enclosure_a, new_status=EnclosurePermitStatus.PERMITTED, now=_T1
    )
    await _observe(
        db_pool, enclosure_id=enclosure_b, new_status=EnclosurePermitStatus.NOT_PERMITTED, now=_T1
    )

    run_a_id = await _start_run_with_fresh_mount(
        deps, db_pool, plan_id=plan_a_id, name="Hutch-A run"
    )
    assert run_a_id is not None

    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        await _start_run_with_fresh_mount(deps, db_pool, plan_id=plan_b_id, name="Hutch-B run")
    failing_ids = {eid for eid, _ in exc_info.value.enclosure_status_summary}
    assert enclosure_b in failing_ids
    assert enclosure_a not in failing_ids


@pytest.mark.integration
async def test_cross_hutch_run_requires_both_hutches_permitted(db_pool: asyncpg.Pool) -> None:
    """A Plan spanning both hutches needs BOTH permits. With hutch A Permitted
    and hutch B NotPermitted, the Plan-AB Run is REFUSED with
    CoverageMismatch (some pass, some fail; the summary names the failing
    enclosure_b). Once hutch B is observed Permitted too, the same Plan-AB Run
    starts."""
    enclosure_a = await _seed_enclosure(db_pool, name="2-BM-A")
    enclosure_b = await _seed_enclosure(db_pool, name="2-BM-B")
    deps, _plan_a_id, _plan_b_id, plan_ab_id = await _seed_two_hutch_topology(
        db_pool, enclosure_a=enclosure_a, enclosure_b=enclosure_b
    )

    await _observe(
        db_pool, enclosure_id=enclosure_a, new_status=EnclosurePermitStatus.PERMITTED, now=_T1
    )
    await _observe(
        db_pool, enclosure_id=enclosure_b, new_status=EnclosurePermitStatus.NOT_PERMITTED, now=_T1
    )

    with pytest.raises(RunEnclosureCoverageMismatchError) as exc_info:
        await _start_run_with_fresh_mount(
            deps, db_pool, plan_id=plan_ab_id, name="Cross-hutch run (B blocked)"
        )
    failing_ids = {eid for eid, _ in exc_info.value.enclosure_status_summary}
    assert enclosure_b in failing_ids
    assert enclosure_a not in failing_ids

    await _observe(
        db_pool, enclosure_id=enclosure_b, new_status=EnclosurePermitStatus.PERMITTED, now=_T2
    )

    run_ab_id = await _start_run_with_fresh_mount(
        deps, db_pool, plan_id=plan_ab_id, name="Cross-hutch run (both permitted)"
    )
    assert run_ab_id is not None
