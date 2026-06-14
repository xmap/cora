"""Pitch alignment at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the `pitch` step of the rotation-axis alignment
chain. Drives the `Hexapod_Pitch` tilt motor (orthogonal to
`Hexapod_Roll`) to remove the rotation axis's out-of-plane tilt
toward/away from the camera. Measured via image-sharpness delta
between 0° and 180° projections of a fiducial sphere: a pitch tilt
moves the sphere closer to / further from the scintillator across
the rotation, modulating focus. Comes fifth and last in the chain
(`resolution -> focus -> center -> roll -> pitch`).

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

To ground the `pitch_alignment` Procedure inventory row on
`docs/deployments/2-bm/procedures.md`, register a new Asset
(`Hexapod_Pitch`), and complete the five-routine alignment chain
in code. After this scenario, the chain's full inventory is
exercised end-to-end.

## Distinction from `roll_alignment`

Both adjust the rotation-axis tilt, but on orthogonal axes:

  - `roll_alignment` corrects tilt about the beam direction (the X
    axis), making the rotation axis perpendicular to the camera Y
    axis. Measured via Y-centroid delta between 0° and 180°.
  - `pitch_alignment` corrects tilt about the in-plane horizontal
    axis (the camera X axis), making the rotation axis perpendicular
    to the beam direction. Measured via image-sharpness delta
    between 0° and 180° (pitch shifts the sphere depth, modulating
    focus).

Pitch is run after roll because the Y-centroid signal used by roll
becomes ambiguous in the presence of large pitch errors (the sphere
defocuses asymmetrically). Roll converges first on a still-pitched
axis; pitch then fine-tunes the remaining tilt.

## Domain shape (synthesized from APS imaging-group practice)

Iterative tilt correction on sharpness delta:

  1. Mount calibration sphere on the kinematic tip.
  2. Rotate to 0°, acquire, measure sphere region sharpness.
  3. Rotate to 180°, acquire, measure sphere region sharpness.
  4. Compute `delta_sharpness = sharpness_at_0 - sharpness_at_180`.
     A non-zero delta means the sphere moved closer to / further
     from the scintillator between the two rotations: pitch is off.
  5. If `|delta_sharpness| > tolerance`: adjust Hexapod_Pitch by
     a small angle proportional to -delta_sharpness, goto 2.
  6. Else: lock the calibrated pitch value.

Typical convergence: 2 iterations starting from a sharpness delta of
~10%. Like roll, the motor's angular range is small (sub-degree);
steps are milliradians.

## Asset stack (rotary + pitch-tilt + detector chain)

  - Aerotech ABRS rotary stage (the rotation axis)
  - Hexapod_Pitch tilt motor (the pitch correction; orthogonal
    to Hexapod_Roll)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (visible-light conversion)

X-correction, Z, roll, and Optique Peter focus-Z motors are omitted:
this routine does not manipulate them. They participate in `center`,
`focus`, `roll`, and `resolution` routines respectively.

## What this scenario surfaces (gap-finding intent)

  - **Sharpness vs centroid signals are not interchangeable.** Both
    roll and pitch correct rotation-axis tilt, but the signals are
    different physical quantities (Y centroid in pixels vs sharpness
    metric in arbitrary units). Whether the polymorphic Check
    payload should have a canonical "tilt-signal" structure across
    sibling routines is a watch item.
  - **Order-of-operations encodes domain knowledge.** Pitch after
    roll after center is not an enforceable invariant; it is a
    convention captured on the per-routine `When to run it` doc
    section. Whether the Practice or Plan should carry a `requires`
    edge to upstream Procedures is a watch item.
  - **Sharpness delta is target-dependent.** Same caveat as
    resolution_alignment: absolute sharpness values are not
    comparable across fiducials. The Check captures `target` so
    downstream queries can filter.
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
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
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

_NOW = datetime(2026, 5, 17, 12, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000358bb")

# Facility hierarchy + operator Actor (Actor.id == _PRINCIPAL_ID)
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000358501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000358a01")

# Capabilities (4: rotary + pseudo-axis pitch + camera + scintillator).
# Hexapod_Pitch is a PseudoAxis (virtual DoF over an underlying solver),
# not a LinearStage. See project_pitch_roll_retag memo for the partial-fix
# rationale; the remaining four hexapod DoFs are deferred until trigger.
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Devices (rotary + pitch-tilt + image chain)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000358a11")
_ASSET_SAMPLE_TOP_PITCH_ID = UUID("01900000-0000-7000-8000-000000358a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000358a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000358a41")

# Recipe ladder
_METHOD_PITCH_ID = UUID("01900000-0000-7000-8000-000000358d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e891")
_PRACTICE_PITCH_ID = UUID("01900000-0000-7000-8000-000000358d11")
_PLAN_PITCH_ID = UUID("01900000-0000-7000-8000-000000358d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000358f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000358f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000358f12")


_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("Hexapod_Pitch", _ASSET_SAMPLE_TOP_PITCH_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
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
        # activate_asset x 4: event_id only (no aggregate id allocated)
        e(),
        e(),
        e(),
        e(),
        # update_asset_partition_rule for Hexapod_Pitch (PseudoAxis): event_id only
        e(),
        # define_method: method_id, event_id
        _METHOD_PITCH_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_PITCH_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_PITCH_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append_activities (lazy open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure: event_id
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: float,
    units: str,
    role: str,
    sampled_at: datetime,
    note: str | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": channel,
        "target_value": target_value,
        "units": units,
        "role": role,
    }
    if note is not None:
        payload["note"] = note
    return ActivityInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload=payload,
        sampled_at=sampled_at,
    )


def _acquire(*, exposure_ms: int, sampled_at: datetime) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_alignment_frame",
            "params": {"exposure_ms": exposure_ms},
        },
        sampled_at=sampled_at,
    )


def _check_sharpness(
    *,
    value: float,
    target: str,
    sampled_at: datetime,
    passed: bool = False,
    evidence: dict[str, Any] | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": "sphere_region_sharpness",
        "passed": passed,
        "source": "tomopy.misc.morph",
        "actual": value,
        "target": target,
    }
    if evidence is not None:
        payload["evidence"] = evidence
    return ActivityInput(
        event_id=uuid4(),
        step_kind="check",
        payload=payload,
        sampled_at=sampled_at,
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _postgres_step_store(db_pool: asyncpg.Pool):
    """Build a PostgresActivityStore for the BC-internal step writer."""
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


@pytest.mark.integration
async def test_pitch_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + 4 Assets (rotary + pitch-tilt + image chain),
    run the 0°/180° sharpness-delta iteration on a fiducial sphere
    until pitch is within tolerance, finalize with a lock setpoint on
    the pitch motor."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Install the 2-BM facility hierarchy + the 4 Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: activate all 4 Devices (Commissioned -> Active) -----

    for asset_id in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_PITCH_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Equipment BC: set partition_rule on the Hexapod_Pitch PseudoAxis -----
    #
    # SolverReference points at the 2bmHXP hexapod-kinematics solver. The
    # constituent topology (Hexapod physical axes feeding the virtual
    # Pitch DoF) is not wired here: the runtime evaluator
    # eval_solver_reference is NotImplemented, and these alignment
    # scenarios use no Plan wires, so the data-substrate retag only needs
    # the rule to construct + pass the Family-membership gate.

    await bind_update_asset_partition_rule(deps)(
        UpdateAssetPartitionRule(
            asset_id=_ASSET_SAMPLE_TOP_PITCH_ID,
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

    # ----- Recipe BC: Method + Practice + Plan for the pitch routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.alignment",
        name="Alignment",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="pitch_alignment",
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
            name="2BM_pitch_practice",
            method_id=_METHOD_PITCH_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_pitch_plan",
            practice_id=_PRACTICE_PITCH_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_PITCH_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM pitch alignment (out-of-plane axis tilt on fiducial sphere)",
            kind="pitch_alignment",
            target_asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_PITCH_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: 2-iteration 0°/180° pitch-tilt correction -----
    #
    # First iteration shows a 0.11 sharpness delta between 0° and 180°
    # (sphere moves toward/away from the scintillator across the rotation);
    # operator dials in a small pitch correction.
    # Second iteration measures 0.02 delta (within tolerance); operator
    # locks the calibrated pitch value.

    t = _NOW
    target = "calibration_sphere"
    iter1 = (
        _setpoint(
            channel="Rotary",
            target_value=0.0,
            units="deg",
            role="rotate_to_0",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_sharpness(value=0.82, target=target, sampled_at=t),
        _setpoint(
            channel="Rotary",
            target_value=180.0,
            units="deg",
            role="rotate_to_180",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_sharpness(
            value=0.71,
            target=target,
            sampled_at=t,
            evidence={"iteration": 1, "delta_sharpness": 0.11, "lever_arm_mm": 75.0},
        ),
        _setpoint(
            channel="Hexapod_Pitch",
            target_value=-0.0008,
            units="deg",
            role="adjust",
            sampled_at=t,
            note="delta_sharpness translated through lever_arm -> pitch correction in deg",
        ),
    )
    iter2 = (
        _setpoint(
            channel="Rotary",
            target_value=0.0,
            units="deg",
            role="rotate_to_0",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_sharpness(value=0.83, target=target, sampled_at=t),
        _setpoint(
            channel="Rotary",
            target_value=180.0,
            units="deg",
            role="rotate_to_180",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_sharpness(
            value=0.81,
            target=target,
            sampled_at=t,
            passed=True,
            evidence={"iteration": 2, "delta_sharpness": 0.02, "tolerance": 0.05},
        ),
    )
    finalize = (
        _setpoint(
            channel="Hexapod_Pitch",
            target_value=-0.0008,
            units="deg",
            role="lock_at_calibrated",
            sampled_at=t,
        ),
    )

    all_entries = iter1 + iter2 + finalize
    assert len(all_entries) == 14, "expected 14 entries for a 2-iteration converged pitch routine"

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=all_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 14

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Procedure stream lifecycle (4 events) -----

    events, version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert version == 4
    assert [e.event_type for e in events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert: each target Asset reached Active lifecycle -----
    #
    # Hexapod_Pitch carries an extra AssetPartitionRuleUpdated event
    # from the SolverReference rule set above; the other 3 Assets have
    # the canonical 3-event sequence.

    for asset_id in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    ):
        asset_events, _ = await deps.event_store.load("Asset", asset_id)
        event_types = [e.event_type for e in asset_events]
        assert event_types == ["AssetRegistered", "AssetFamilyAdded", "AssetActivated"]

    pitch_events, _ = await deps.event_store.load("Asset", _ASSET_SAMPLE_TOP_PITCH_ID)
    pitch_event_types = [e.event_type for e in pitch_events]
    assert pitch_event_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetActivated",
        "AssetPartitionRuleUpdated",
    ]

    # ----- Assert: 14 step entries land in the projection in canonical order -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 14
    assert [r["step_kind"] for r in rows] == [
        "setpoint",
        "action",
        "check",  # iteration 1 @ 0°
        "setpoint",
        "action",
        "check",  # iteration 1 @ 180°
        "setpoint",  # iteration 1 adjust
        "setpoint",
        "action",
        "check",  # iteration 2 @ 0°
        "setpoint",
        "action",
        "check",  # iteration 2 @ 180° (passed)
        "setpoint",  # finalize (lock_at_calibrated)
    ]
