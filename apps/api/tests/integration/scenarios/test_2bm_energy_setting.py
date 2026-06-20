"""Setting the beam energy at APS 2-BM (the coordinating operation).

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Operation, Recipe, Equipment

Models "set energy" as one coordinated operation. Per the staff-authored
docs2bm energy-change IOC, changing energy drives the energy-tracking optic
axes together to their per-energy positions. CORA expresses that intent as a
Procedure (Operation BC) realizing the `cora.capability.energy_change`
Capability via a `beamline_energy_change` Method: the Procedure records the
coordinated move across the five energy-driven facets (the DMM Bragg arms +
M2 vertical offset, and the sample-slit vertical pair) as Setpoint / Action /
Check steps, mirroring test_2bm_motor_homing.py.

The Method takes a FREE energy value (keV): the per-axis energy curves
interpolate, so an operator can request an energy between the saved points,
not just the configured menu. This scenario demonstrates that at 22.0 keV,
which sits between the saved 18 and 25 keV points; the per-axis setpoints are
the (PROVISIONAL) positions the per-energy curves yield there by interpolation.

What this proves (and what it does not): it proves the coordinating shape
holds together (a Capability + Method + a Procedure recording the multi-axis
move across heterogeneous axes, deg arms + mm slits/offset). This scenario
RECORDS the coordinated move as logbook activities (the motion artifact); it
does not conduct the facets through the Conductor. The pure interpolation
kernel that turns an energy into a position is now wired and proven end-to-end
in test_pseudoaxis_roundtrip.py, so the positions would be computed live on a
real conduct. Three prerequisites still stand between here and a real beamline
move: (1) real saved positions (the curves seeded today are PROVISIONAL
placeholders, hence the illustrative setpoints recorded below), (2) per-facet
constituent wiring that names each physical motor, and (3) live EPICS dispatch.
The per-axis energy curves themselves are established by
the energy-curve scenario (test_2bm_energy_curves_setup.py); here each facet
is a bare PseudoAxis the operation drives. The operator's EnergyChange Decision
(test_2bm_energy_change.py) is the forward-looking justification; this
Procedure is the motion artifact.

## Asset stack

```
2-BM (Unit)
+-- FrontEndDrive (Device)               MotionController
    +-- Monochromator (Device)           Monochromator  (driven by FrontEndDrive)
    |   +-- Monochromator_BraggArmUpstream     PseudoAxis
    |   +-- Monochromator_BraggArmDownstream   PseudoAxis
    |   +-- Monochromator_M2Y                  PseudoAxis
    +-- SampleSlit (Device)              Slit           (driven by FrontEndDrive)
        +-- SampleSlit_VerticalTop             PseudoAxis
        +-- SampleSlit_VerticalBottom          PseudoAxis
```
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_asset_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.recipe.aggregates.capability import ExecutorShape
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.update_method_parameters_schema import UpdateMethodParametersSchema
from cora.recipe.features.update_method_parameters_schema import (
    bind as bind_update_method_schema,
)
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 6, 16, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004c0cc1")

# Scenario tag: 4c0 (set energy: the coordinating operation).

_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-0000004c0a01")

_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))
_CAP_MONOCHROMATOR_ID = family_stream_id(FamilyName("Monochromator"))
_CAP_SLIT_ID = family_stream_id(FamilyName("Slit"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))

_FRONTENDDRIVE_ID = UUID("01900000-0000-7000-8000-0000004c0a31")
_MONOCHROMATOR_ID = UUID("01900000-0000-7000-8000-0000004c0a12")
_SAMPLE_SLIT_ID = UUID("01900000-0000-7000-8000-0000004c0a14")

_CAPABILITY_ENERGY_CHANGE_ID = UUID("01900000-0000-7000-8000-0000004c0e01")

_DEVICES = (
    DeviceSpec("FrontEndDrive", _FRONTENDDRIVE_ID, "MotionController", _CAP_MOTION_CONTROLLER_ID),
    DeviceSpec(
        "Monochromator",
        _MONOCHROMATOR_ID,
        "Monochromator",
        _CAP_MONOCHROMATOR_ID,
        controller_id=_FRONTENDDRIVE_ID,
    ),
    DeviceSpec(
        "SampleSlit", _SAMPLE_SLIT_ID, "Slit", _CAP_SLIT_ID, controller_id=_FRONTENDDRIVE_ID
    ),
)

# The requested energy: 22.0 keV sits BETWEEN the saved 18 and 25 keV curve
# points, exercising the free-keV interpolation the operation is designed for.
_TARGET_ENERGY_KEV = 22.0

# The five energy-driven facets + the PROVISIONAL per-axis setpoints the
# per-energy curves would yield at 22.0 keV by interpolation (illustrative
# placeholders recorded here; the live kernel computes them on a real conduct).
# (facet_name, parent_id, units, setpoint)
_AXES: tuple[tuple[str, UUID, str, float], ...] = (
    ("Monochromator_BraggArmUpstream", _MONOCHROMATOR_ID, "deg", 0.76),
    ("Monochromator_BraggArmDownstream", _MONOCHROMATOR_ID, "deg", 0.76),
    ("Monochromator_M2Y", _MONOCHROMATOR_ID, "mm", 1.21),
    ("SampleSlit_VerticalTop", _SAMPLE_SLIT_ID, "mm", 0.19),
    ("SampleSlit_VerticalBottom", _SAMPLE_SLIT_ID, "mm", -0.19),
)

# Free-keV energy parameter: a number with a keV unit annotation, bounded to the
# beamline's operating range. NOT a discrete index; the curves interpolate.
_METHOD_PARAMETERS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "energy": {
            "type": "number",
            "minimum": 1,
            "maximum": 100,
            "unit": {"system": "udunits", "code": "keV"},
        },
    },
    "required": ["energy"],
}


def _id_queue() -> list[UUID]:
    """FixedIdGenerator queue: facility prefix + a generous anonymous tail. The
    facet / method / procedure ids are captured from handler return values; the
    internal step / logbook ids come from the tail (not asserted on)."""
    return [
        *facility_id_prefix(unit_id=_2BM_UNIT_ID, devices=_DEVICES),
        *[uuid4() for _ in range(80)],
    ]


def _setpoint(
    *, channel: str, target_value: float, units: str, sampled_at: datetime
) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload={
            "channel": channel,
            "target_value": target_value,
            "units": units,
            "role": "energy_move",
        },
        sampled_at=sampled_at,
    )


def _action(*, action_name: str, sampled_at: datetime, **params: Any) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(*, channel: str, expected: float, sampled_at: datetime) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="check",
        payload={
            "channel": channel,
            "passed": True,
            "source": "encoder_readback",
            "expected": expected,
            "actual": expected,
        },
        sampled_at=sampled_at,
    )


def _postgres_step_store(db_pool: asyncpg.Pool):
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_energy_setting_records_a_coordinated_move(db_pool: asyncpg.Pool) -> None:
    """Define the energy_change Capability + beamline_energy_change Method
    (free-keV), then register + run an energy_setting Procedure that records the
    coordinated move across the five energy facets to their per-energy
    positions. Assert the Procedure FSM and the recorded step sequence."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- The five energy-driven facets (PseudoAxis sub-modules) -----
    await bind_define_family(deps)(
        DefineFamily(name="PseudoAxis", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    facet_ids: dict[str, UUID] = {}
    for facet_name, parent_id, _units, _setpoint_value in _AXES:
        facet_id = await bind_register_asset(deps)(
            RegisterAsset(name=facet_name, tier=AssetTier.DEVICE, parent_id=parent_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        facet_ids[facet_name] = facet_id
        await bind_add_asset_family(deps)(
            AddAssetFamily(asset_id=facet_id, family_id=_CAP_PSEUDO_AXIS_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: the energy_change Capability + beamline_energy_change Method -----
    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ENERGY_CHANGE_ID,
        code="cora.capability.energy_change",
        name="Energy Change",
        shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
    )
    method_id = await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ENERGY_CHANGE_ID,
            name="beamline_energy_change",
            needed_family_ids=frozenset({_CAP_MONOCHROMATOR_ID, _CAP_SLIT_ID, _CAP_PSEUDO_AXIS_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_method_schema(deps)(
        UpdateMethodParametersSchema(
            method_id=method_id,
            parameters_schema=_METHOD_PARAMETERS_SCHEMA,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the energy_setting Procedure -----
    procedure_id = await bind_register_procedure(deps)(
        RegisterProcedure(
            name=f"2-BM set energy to {_TARGET_ENERGY_KEV} keV",
            # kind names the specific operation, distinct from the energy_change
            # Capability code (as motor_homing's kind sits under maintenance).
            kind="energy_setting",
            target_asset_ids=frozenset(facet_ids.values()),
            capability_id=_CAPABILITY_ENERGY_CHANGE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Record the coordinated move: setpoint per facet, one action, check per facet -----
    setpoints = tuple(
        _setpoint(channel=name, target_value=value, units=units, sampled_at=_NOW)
        for name, _parent, units, value in _AXES
    )
    action = _action(
        action_name="coordinate_energy_move",
        sampled_at=_NOW,
        energy_kev=_TARGET_ENERGY_KEV,
        axis_count=len(_AXES),
    )
    checks = tuple(
        _check(channel=f"{name}.readback", expected=value, sampled_at=_NOW)
        for name, _parent, _units, value in _AXES
    )
    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(*setpoints, action, *checks),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete(deps)(
        CompleteProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ===== Assertions =====
    procedure_events, _ = await deps.event_store.load("Procedure", procedure_id)
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]
    genesis = procedure_events[0].payload
    assert genesis["kind"] == "energy_setting"
    assert genesis["capability_id"] == str(_CAPABILITY_ENERGY_CHANGE_ID)
    assert set(genesis["target_asset_ids"]) == {str(fid) for fid in facet_ids.values()}

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 "
            "AND payload->>'result' IS DISTINCT FROM 'in_flight'",
            procedure_id,
        )
    kinds = [r["step_kind"] for r in rows]
    # The coordinated move recorded one setpoint + one readback check per facet
    # plus the single coordinating action (the five axes driven together).
    assert len(kinds) == 11
    assert kinds.count("setpoint") == 5
    assert kinds.count("action") == 1
    assert kinds.count("check") == 5
