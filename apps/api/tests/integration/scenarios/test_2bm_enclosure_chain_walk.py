"""Enclosure permit on an ANCESTOR Asset gates Run.start at APS 2-BM.

cluster: Staging
archetype: gate
bc_primary: Enclosure
bc_touches: Enclosure, Run, Recipe, Equipment, Subject

The end-to-end payoff of the chain walk (Slice 5). Where
test_2bm_enclosure_preflight binds the Enclosure DIRECTLY to the
Plan's Asset, this scenario binds it to that Asset's PARENT: the Plan
binds only a Device, and the Enclosure sits on the beamline Unit above
it. Only the parent_id ancestor walk (AssetLookup.ancestors_of, read by
start_run against the real proj_equipment_asset_summary) brings the
Unit into scope so the gate sees the Enclosure.

  - test_chain_walk_gates_run_via_ancestor_enclosure: with the walk on
    (PostgresAssetLookup), the Unit's Unknown Enclosure REFUSES the Run;
    walking it to Permitted lets the Run start.
  - test_without_walk_ancestor_enclosure_silently_passes: the load-
    bearing control. With the walk off (empty asset_lookup), the very
    same parent-bound Unknown Enclosure is never brought into scope, so
    the Run silently starts. The contrast is the proof that L-pre-1
    ("derive scope from the Asset chain") is load-bearing only because
    of the walk.
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
from cora.equipment.features import (
    add_asset_family,
    decommission_asset,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunRequiresPermittedEnclosureError
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.shared.identity import MonitorSourceId
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_T0 = datetime(2026, 6, 12, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 12, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000e001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000e002")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e6f1")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000e003"))


async def _drain_enclosure(db_pool: asyncpg.Pool) -> None:
    from cora.infrastructure.projection import ProjectionRegistry, drain_projections

    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_chain(
    db_pool: asyncpg.Pool, *, walk: bool
) -> tuple[Kernel, UUID, UUID, UUID, UUID]:
    """Seed a 2-BM Unit + a Device UNDER it, a Plan binding the Device, and
    the rest of the Run chain. Drains the equipment projection so the
    Device -> Unit parent_id edge is visible to the walk.

    `walk=True` wires the real PostgresAssetLookup so start_run climbs the
    chain; `walk=False` leaves the empty default so the walk is inert (the
    control). Returns (deps, plan_id, subject_id, unit_id, device_id).
    """
    asset_lookup = PostgresAssetLookup(db_pool) if walk else None
    deps = build_postgres_deps(
        db_pool, now=_T0, ids=[uuid4() for _ in range(40)], asset_lookup=asset_lookup
    )
    deps = dataclasses.replace(deps, enclosure_lookup=PostgresEnclosureLookup(db_pool))

    cap_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    unit_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="2-BM beamline", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    device_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector", tier=AssetTier.DEVICE, parent_id=unit_id, facility_code=None
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=device_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID, name="XRF Fly Scan", needed_family_ids=frozenset({cap_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="2-BM Pilot Scan", practice_id=practice_id, asset_ids=frozenset({device_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    subject_id = await register_subject.bind(deps)(
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
    await drain_equipment_projections(db_pool)
    return deps, plan_id, subject_id, unit_id, device_id


async def _seed_enclosure(db_pool: asyncpg.Pool, *, containing_asset_id: UUID) -> UUID:
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(3)])
    suffix = uuid4().hex[:8]
    eid = await register_enclosure.bind(deps)(
        RegisterEnclosure(
            name=f"2-BM-beamline-hutch-{suffix}", containing_asset_id=containing_asset_id
        ),
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


@pytest.mark.integration
async def test_chain_walk_gates_run_via_ancestor_enclosure(db_pool: asyncpg.Pool) -> None:
    """Plan binds the Device; the Unknown Enclosure sits on its parent Unit.
    The walk brings the Unit into scope -> REFUSED. Walk to Permitted -> the
    Run starts."""
    deps, plan_id, subject_id, unit_id, _device_id = await _seed_chain(db_pool, walk=True)
    enclosure_id = await _seed_enclosure(db_pool, containing_asset_id=unit_id)

    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        await start_run.bind(deps)(
            StartRun(name="Refused via ancestor", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    failing = exc_info.value.enclosure_status_summary
    assert any(eid == enclosure_id for eid, _ in failing)

    await _observe(
        db_pool, enclosure_id=enclosure_id, new_status=EnclosurePermitStatus.PERMITTED, now=_T1
    )

    run_id = await start_run.bind(deps)(
        StartRun(name="Allowed when ancestor Permitted", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert run_id is not None


@pytest.mark.integration
async def test_without_walk_ancestor_enclosure_silently_passes(db_pool: asyncpg.Pool) -> None:
    """Load-bearing control: same parent-bound Unknown Enclosure, but the
    walk is off (empty asset_lookup). The Unit is never brought into scope,
    so the Run silently starts -- the exact gap the walk closes."""
    deps, plan_id, subject_id, unit_id, _device_id = await _seed_chain(db_pool, walk=False)
    await _seed_enclosure(db_pool, containing_asset_id=unit_id)

    run_id = await start_run.bind(deps)(
        StartRun(name="Silent pass without walk", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert run_id is not None


@pytest.mark.integration
async def test_decommissioned_ancestor_with_active_notpermitted_enclosure_still_refuses(
    db_pool: asyncpg.Pool,
) -> None:
    """Safety regression: a Decommissioned ANCESTOR must NOT suppress its own
    still-Active NotPermitted Enclosure. The Unit is decommissioned but its
    interlock Enclosure stays Active + NotPermitted (decommission_asset has
    no Enclosure cascade). The walk must still bring the retired Unit into
    scope so the gate sees the live NotPermitted Enclosure and REFUSES the
    Run. Filtering Decommissioned ancestors out of the widening would
    silently admit the Run into an un-permitted hutch."""
    deps, plan_id, subject_id, unit_id, _device_id = await _seed_chain(db_pool, walk=True)
    enclosure_id = await _seed_enclosure(db_pool, containing_asset_id=unit_id)
    await _observe(
        db_pool,
        enclosure_id=enclosure_id,
        new_status=EnclosurePermitStatus.NOT_PERMITTED,
        now=_T1,
    )

    # Retire the containing Unit. Its Enclosure is untouched (Active + NotPermitted).
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=unit_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(db_pool)

    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        await start_run.bind(deps)(
            StartRun(
                name="Must refuse via decommissioned ancestor",
                plan_id=plan_id,
                subject_id=subject_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert any(eid == enclosure_id for eid, _ in exc_info.value.enclosure_status_summary)
