"""Roll alignment at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the `roll` step of the rotation-axis alignment
chain. Drives the `Hexapod_Roll` tilt motor (under the rotation
stage) to make the rotation axis perpendicular to the camera Y axis,
so that a fiducial sphere mounted on the rotation axis traces a
horizontal line at the same Y across all rotation angles. Comes
fourth in the five-routine chain (`resolution -> focus -> center ->
roll -> pitch`).

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

To ground the `roll_alignment` Procedure inventory row on
`docs/deployments/2-bm/procedures.md`, and to register a new Asset
(`Hexapod_Roll`) that no prior scenario has touched. Per
[[project_pilot_docs_design]] no doc page may name an aggregate until
a scenario test registers it; this file unlocks the roll-tilt motor
in the 2-BM Asset inventory.

## Distinction from `center_alignment`

Both routines use the same 0°/180° measurement scheme on a fiducial
sphere, but adjust different motors against different image axes:

  - `center_alignment` adjusts `Sample_top_X` to make the sphere
    centroid X coincide at 0° and 180° (the rotation axis runs
    through the sample's lateral midline).
  - `roll_alignment` adjusts `Hexapod_Roll` to make the sphere
    centroid Y coincide at 0° and 180° (the rotation axis is
    vertical, perpendicular to the camera Y axis).

Center can succeed while roll fails: the sphere can be on-axis in X
yet trace a diagonal Y track if the rotation axis tilts about the
beam direction. Roll runs after center because the X centering
provides a stable reference; on a centered sphere, any Y delta
between 0° and 180° is purely a roll-tilt signature.

## Domain shape (synthesized from APS imaging-group practice)

Iterative tilt correction:

  1. Mount calibration sphere on the kinematic tip.
  2. Rotate to 0°, acquire, note sphere centroid Y.
  3. Rotate to 180°, acquire, note sphere centroid Y.
  4. Compute Y delta = (centroid_at_180 - centroid_at_0).
  5. If |delta_y| > tolerance: adjust Hexapod_Roll by a small
     angle proportional to -delta_y / (2 * lever_arm), goto 2.
  6. Else: write the calibrated roll value to the
     `Hexapod_Roll` PV. Done.

Typical convergence: 2 iterations starting from a few-pixel Y delta.
Roll moves are small-angle (milliradians or arc-seconds); the motor's
absolute position carries the calibration after the routine completes.

## Asset stack (rotary + roll-tilt + detector chain)

  - Aerotech ABRS rotary stage (the rotation axis)
  - Hexapod_Roll tilt motor (the roll correction; a goniometer or
    wedge stage beneath the sample-top)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (visible-light conversion)

X-correction motor, Z motor, and Optique Peter focus-Z are omitted:
this routine does not manipulate them. They participate in the
`center`, `focus`, and `resolution` routines respectively.

## What this scenario surfaces (gap-finding intent)

  - **Mount tilt vs axis tilt are not distinguishable from a single
    sphere measurement.** If the sphere is mounted off-center, its
    Y trace can vary at 0° vs 180° even when the rotation axis is
    perfectly vertical (mount-induced wobble). The scenario does not
    encode mount-tilt diagnosis; a real procedure may swap to a
    multi-fiducial target. Whether the Subject BC should model
    fiducial geometry is a watch item.
  - **Lever-arm calibration is operator tribal knowledge.** The
    Hexapod_Roll motor's angular step does not map directly to
    pixels; the conversion depends on sample mount geometry and
    must be calibrated separately. The scenario captures the
    conversion as a `lever_arm_mm` evidence key but does not enforce
    its presence. Whether the Method should require a calibration
    Setpoint before the loop starts is a watch item.
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

_NOW = datetime(2026, 5, 17, 11, 45, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000357bb")

# Facility hierarchy + operator Actor (Actor.id == _PRINCIPAL_ID)
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000357501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000357a01")

# Capabilities (4: rotary + pseudo-axis roll + camera + scintillator).
# Hexapod_Roll is a PseudoAxis (virtual DoF over an underlying solver),
# not a LinearStage. See project_pitch_roll_retag memo for the partial-fix
# rationale; the remaining four hexapod DoFs are deferred until trigger.
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_PSEUDO_AXIS_ID = family_stream_id(FamilyName("PseudoAxis"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Devices (rotary + roll-tilt + image chain)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000357a11")
_ASSET_SAMPLE_TOP_ROLL_ID = UUID("01900000-0000-7000-8000-000000357a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000357a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000357a41")

# Recipe ladder
_METHOD_ROLL_ID = UUID("01900000-0000-7000-8000-000000357d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ee29")
_PRACTICE_ROLL_ID = UUID("01900000-0000-7000-8000-000000357d11")
_PLAN_ROLL_ID = UUID("01900000-0000-7000-8000-000000357d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000357f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000357f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000357f12")


_DEVICES = (
    DeviceSpec(
        "Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID
    ),
    DeviceSpec("Hexapod_Roll", _ASSET_SAMPLE_TOP_ROLL_ID, "PseudoAxis", _CAP_PSEUDO_AXIS_ID),
    DeviceSpec("Oryx_5MP_camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec(
        "Scintillator_LuAG", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID
    ),
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
        # update_asset_partition_rule for Hexapod_Roll (PseudoAxis): event_id only
        e(),
        # define_method: method_id, event_id
        _METHOD_ROLL_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_ROLL_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_ROLL_ID,
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


def _check_y(
    *,
    value_px: float,
    sampled_at: datetime,
    passed: bool = False,
    evidence: dict[str, Any] | None = None,
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": "sphere_centroid_y_px",
        "passed": passed,
        "source": "image_analysis",
        "actual": value_px,
        "units": "px",
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
async def test_roll_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + 4 Assets (rotary + roll-tilt + image chain), run
    the 0°/180° roll-tilt iteration on a fiducial sphere until the Y
    delta is within tolerance, finalize with a lock setpoint on the
    roll motor."""
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

    # ----- Recipe BC: Method + Practice + Plan for the roll routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.alignment",
        name="Alignment",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="roll_alignment",
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
            name="2BM_roll_practice",
            method_id=_METHOD_ROLL_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_roll_plan",
            practice_id=_PRACTICE_ROLL_ID,
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

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM roll alignment (vertical-axis tilt on fiducial sphere)",
            kind="roll_alignment",
            target_asset_ids=frozenset(
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
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: 2-iteration 0°/180° roll-tilt correction -----
    #
    # First iteration shows a 3.0 px Y delta between 0° and 180° (rotation
    # axis is tilted); operator dials in a small roll correction.
    # Second iteration measures 0.3 px delta (within tolerance); operator
    # locks the calibrated roll value.

    t = _NOW
    iter1 = (
        _setpoint(
            channel="Aerotech_ABRS_rotary",
            target_value=0.0,
            units="deg",
            role="rotate_to_0",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_y(value_px=512.0, sampled_at=t),
        _setpoint(
            channel="Aerotech_ABRS_rotary",
            target_value=180.0,
            units="deg",
            role="rotate_to_180",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_y(
            value_px=515.0,
            sampled_at=t,
            evidence={"iteration": 1, "delta_y_px": 3.0, "lever_arm_mm": 75.0},
        ),
        _setpoint(
            channel="Hexapod_Roll",
            target_value=-0.0011,
            units="deg",
            role="adjust",
            sampled_at=t,
            note="delta_y_px / (2 * lever_arm) -> roll correction in deg",
        ),
    )
    iter2 = (
        _setpoint(
            channel="Aerotech_ABRS_rotary",
            target_value=0.0,
            units="deg",
            role="rotate_to_0",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_y(value_px=512.2, sampled_at=t),
        _setpoint(
            channel="Aerotech_ABRS_rotary",
            target_value=180.0,
            units="deg",
            role="rotate_to_180",
            sampled_at=t,
        ),
        _acquire(exposure_ms=150, sampled_at=t),
        _check_y(
            value_px=512.5,
            sampled_at=t,
            passed=True,
            evidence={"iteration": 2, "delta_y_px": 0.3, "tolerance_px": 0.5},
        ),
    )
    finalize = (
        _setpoint(
            channel="Hexapod_Roll",
            target_value=-0.0011,
            units="deg",
            role="lock_at_calibrated",
            sampled_at=t,
        ),
    )

    all_entries = iter1 + iter2 + finalize
    assert len(all_entries) == 14, "expected 14 entries for a 2-iteration converged roll routine"

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
    # Hexapod_Roll carries an extra AssetPartitionRuleUpdated event
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

    roll_events, _ = await deps.event_store.load("Asset", _ASSET_SAMPLE_TOP_ROLL_ID)
    roll_event_types = [e.event_type for e in roll_events]
    assert roll_event_types == [
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
