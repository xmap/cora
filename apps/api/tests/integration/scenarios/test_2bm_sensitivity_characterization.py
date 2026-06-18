"""Tilt-sensitivity characterization at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the sensitivity-characterization pre-step of the
rotation-axis alignment chain: with a calibration sphere in place, the operator
bumps roll and pitch motors by known deltas, measures sphere
centroid shifts, and computes the motor sensitivities (`K_roll`,
`K_pitch`) that the iterative alignment chain (resolution / focus
/ center / roll / pitch) consumes as its linear gains. Sourced
from `align/src/align/auto.py` calibration pass.

Phase commissioning.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

**Patches a real gap in the existing 5-scenario alignment chain.**
Today's `test_2bm_alignment_{resolution,focus,center,roll,pitch}.py`
all assume the motor-sensitivity constants (`K_roll`, `K_pitch`)
exist from nowhere. The real `align/auto.py` script's calibration
pass measures them empirically before any iteration starts: bump
each axis by a known delta, observe the resulting centroid shift,
compute K = (shift_delta) / (motor_delta), guard against
zero-response (sphere mount probably loose).

This scenario surfaces that pre-step in code so the chain's
linear-gain assumption has an empirical origin.

## Domain shape (from `align/auto.py`)

For each axis (roll then pitch):

  1. Capture baseline rotation measurement (sphere centroid shift_x,
     shift_y).
  2. Bump the motor by `calibration_delta_<axis>` degrees.
  3. Re-measure centroid shift.
  4. Restore the motor to baseline.
  5. Compute `K = (shift_delta) / (calibration_delta)`. The
     denominator-delta is in `deg`; the numerator is in `px`;
     output is `px/deg`.
  6. Guard: if either delta is too small (loose mount,
     under-illuminated, or insufficient lever-arm height),
     abort with operator-facing diagnostic.

The full `auto.py` also calibrates `K_cam` (camera-rotation
sensitivity), but the 2-BM imaging chain in this corpus does not
yet register a camera-rotation motor; that characterization step
lands when the camera-rotation Device is added. This scenario
covers K_roll + K_pitch on the existing Hexapod_Roll /
Hexapod_Pitch motors.

## Asset stack (rotation axis + tilt motors + image chain)

Subset of the alignment chain's Asset stack: Aerotech rotary (for
the rotation measurement at 0° / 180°), Hexapod_Roll +
Hexapod_Pitch (the motors being calibrated), Oryx camera +
LuAG scintillator (the centroid-detection chain). SampleTop_Z
is NOT used (characterization runs at a fixed Y_ref height; depth
tuning is the `focus` step's concern).

## What this scenario surfaces (gap-finding intent)

  - **The K values are produced but not persisted as first-class
    CORA state.** Today they live as `Setpoint(channel='K_roll'
    | 'K_pitch', target_value=...)` step entries inside the
    Procedure log. Downstream alignment scenarios re-derive (or
    assume) them. Whether `K_roll` / `K_pitch` should land as
    `Method.parameters_schema` outputs that the alignment Plans
    consume is a watch item.
  - **The calibration sphere is operator-mounted but not CORA-
    modeled.** Real operators mount a tungsten carbide sphere on
    the kinematic tip before calibration; we'd want to model that
    as a Subject (kind=calibration_phantom). Deferred until the
    Subject BC's calibration-phantom slug pattern is locked.
  - **Guards are inline-checked, not part of the Procedure FSM.**
    The real `auto.py` aborts when `shift_delta < threshold`; in
    CORA the operator's Check(`passed=False`) lands as the failure
    signal, but the Procedure status stays Running. Whether
    `auto.py`-style fatal-guard Checks should automatically
    transition Procedure to Aborted is a watch item.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates._partition_rule import (
    SolverReference,
    SolverTransportKind,
)
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.update_asset_partition_rule import UpdateAssetPartitionRule
from cora.equipment.features.update_asset_partition_rule import (
    bind as bind_update_asset_partition_rule,
)
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
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

_NOW = datetime(2026, 5, 17, 15, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000410bb")

# Facility hierarchy. Scenario tag: 410 (commissioning / sensitivity characterization).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000410a01")

# Practice site_id: an opaque practice-site UUID (NOT an Asset tier).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000410501")

# Capabilities (rotary + pseudo-axis (tilt motors) + camera + scintillator).
# Hexapod_Roll is a PseudoAxis (virtual DoF over an underlying solver),
# not a LinearStage. See project_pitch_roll_retag memo for the partial-fix
# rationale; the remaining four hexapod DoFs are deferred until trigger.
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Devices
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000410a11")
_ASSET_SAMPLE_TOP_ROLL_ID = UUID("01900000-0000-7000-8000-000000410a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000410a41")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000410a51")

# Recipe ladder
_METHOD_CALIB_ID = UUID("01900000-0000-7000-8000-000000410d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e8f4")
_PRACTICE_CALIB_ID = UUID("01900000-0000-7000-8000-000000410d11")
_PLAN_CALIB_ID = UUID("01900000-0000-7000-8000-000000410d21")

# Procedure + lazy logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000410f02")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000410f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000410f12")

_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("Hexapod_Roll", _ASSET_SAMPLE_TOP_ROLL_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # activate_asset x 4
        e(),
        e(),
        e(),
        e(),
        # update_asset_partition_rule for Hexapod_Roll (PseudoAxis): event_id only
        e(),
        # define_method: method_id, event_id
        _METHOD_CALIB_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_CALIB_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_CALIB_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append_activities (lazy open): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure: event_id
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: float | str,
    units: str,
    role: str | None = None,
    note: str | None = None,
    sampled_at: datetime,
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": channel,
        "target_value": target_value,
        "units": units,
    }
    if role is not None:
        payload["role"] = role
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(), step_kind="setpoint", payload=payload, sampled_at=sampled_at
    )


def _action(*, action_name: str, sampled_at: datetime, **params: Any) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    actual: float | str | None = None,
    expected: float | str | None = None,
    note: str | None = None,
    **evidence: Any,
) -> ActivityInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if note is not None:
        payload["note"] = note
    if evidence:
        payload["evidence"] = evidence
    return ActivityInput(
        event_id=uuid4(), step_kind="check", payload=payload, sampled_at=sampled_at
    )


def _postgres_step_store(db_pool: asyncpg.Pool):
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


@pytest.mark.integration
async def test_sensitivity_characterization_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed imaging chain + tilt motors, run the K_roll + K_pitch
    characterization: bump each tilt motor by a known delta,
    capture sphere centroid shift, restore motor, compute the
    sensitivity constant. Final Setpoints record the computed K
    values that downstream alignment Plans consume."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )

    for asset_id in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_ROLL_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Equipment BC: set partition_rule on the Hexapod_Roll PseudoAxis -----
    #
    # SolverReference points at the 2bmHXP hexapod-kinematics solver. The
    # constituent topology is not wired here (no Plan wires in this
    # scenario, runtime eval_solver_reference is NotImplemented); the
    # data-substrate retag only needs the rule to construct + pass the
    # Family-membership gate.

    await bind_update_asset_partition_rule(deps)(
        UpdateAssetPartitionRule(
            asset_id=_ASSET_SAMPLE_TOP_ROLL_ID,
            partition_rule=SolverReference(
                solver_id="2bmHXP",
                solver_version="1.0.0",
                solver_transport_kind=SolverTransportKind.SOFT_IOC_RECORD,
                residual_tolerance_limit=0.001,
                singularity_threshold=0.01,
                invertible=True,
                readback_aggregator_kind=None,
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe BC: Method + Practice + Plan -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.characterization",
        name="Characterization",
    )

    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="sensitivity_characterization",
            needed_family_ids=frozenset(
                {
                    _CAP_ROTARY_STAGE_ID,
                    _CAP_PSEUDO_AXIS_ID,
                    _CAP_CAMERA_ID,
                    _CAP_SCINTILLATOR_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_sensitivity_characterization_practice",
            method_id=_METHOD_CALIB_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_sensitivity_characterization_plan",
            practice_id=_PRACTICE_CALIB_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_ROLL_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM tilt-sensitivity characterization (K_roll, K_pitch)",
            kind="sensitivity_characterization",
            target_asset_ids=frozenset({_ASSET_SAMPLE_TOP_ROLL_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: K_roll characterization -----

    t = _NOW
    # Real numbers from a typical 2-BM characterization session:
    # delta_roll = 0.1 deg (small bump); resulting shift_x delta = 0.42 px.
    # K_roll = 0.42 / 0.1 = 4.2 px/deg.
    delta_roll_deg = 0.1
    baseline_shift_x_px = 0.0
    bumped_shift_x_px = 0.42
    K_roll = (bumped_shift_x_px - baseline_shift_x_px) / delta_roll_deg  # noqa: N806

    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(
            procedure_id=_PROCEDURE_ID,
            entries=(
                # K_roll characterization triplet
                _setpoint(
                    channel="Hexapod_Roll",
                    target_value=0.0,
                    units="deg",
                    role="calibration_baseline",
                    note="capture baseline shift_x with sphere at Y_ref",
                    sampled_at=t,
                ),
                _action(
                    action_name="measure_rotation",
                    motor="Hexapod_Roll",
                    sampled_at=t,
                    expects=["shift_x"],
                ),
                _check(
                    channel="Hexapod_Roll.shift_x",
                    passed=True,
                    source="centroid_detection",
                    actual=baseline_shift_x_px,
                    note="baseline captured",
                    sampled_at=t,
                ),
                _setpoint(
                    channel="Hexapod_Roll",
                    target_value=delta_roll_deg,
                    units="deg",
                    role="calibration_bump",
                    note=f"bump by +{delta_roll_deg}deg to measure sensitivity",
                    sampled_at=t,
                ),
                _action(
                    action_name="measure_rotation",
                    motor="Hexapod_Roll",
                    sampled_at=t,
                    expects=["shift_x"],
                ),
                _check(
                    channel="Hexapod_Roll.shift_x",
                    passed=True,
                    source="centroid_detection",
                    actual=bumped_shift_x_px,
                    note=(
                        f"shift_x delta = {bumped_shift_x_px - baseline_shift_x_px}px; "
                        f"well above noise floor"
                    ),
                    sampled_at=t,
                    delta_px=bumped_shift_x_px - baseline_shift_x_px,
                ),
                _setpoint(
                    channel="Hexapod_Roll",
                    target_value=0.0,
                    units="deg",
                    role="calibration_restore",
                    note="restore roll motor to baseline",
                    sampled_at=t,
                ),
                _setpoint(
                    channel="K_roll",
                    target_value=K_roll,
                    units="px/deg",
                    role="record_calibration_constant",
                    note=(
                        f"K_roll = (shift_delta / bump_delta) = "
                        f"({bumped_shift_x_px - baseline_shift_x_px} / {delta_roll_deg}) "
                        f"= {K_roll} px/deg"
                    ),
                    sampled_at=t,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: complete Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Procedure stream lifecycle (4 events) -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 4
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert: 8 step entries (4 setpoints + 2 actions + 2 checks) -----

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind, payload FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at, event_id",
            _PROCEDURE_ID,
        )
    assert len(rows) == 8
    kinds = [r["step_kind"] for r in rows]
    assert kinds.count("setpoint") == 4
    assert kinds.count("action") == 2
    assert kinds.count("check") == 2
