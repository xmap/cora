"""Center alignment at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe, Calibration

Scenario test for the rotation-axis "center" alignment routine at 2-BM
micro-CT, as performed by operators today at mechanically-similar 2-BM
via the `xray-imaging/adjust` CLI. Composes the full Equipment + Recipe
+ Operation BC stack end-to-end for one real beamline routine.

See [[project_pilot_docs_design]] for the phase / file-naming taxonomy
this scenario fits into.

## Why this test exists

The value is not a green CI light; it is **gap-surfacing**: do the
synthetic-BC-shape decisions hold up when expressed against a real
operator workflow? Each gap surfaced becomes a watch item or design
memo addition, not a fix in this file.

## Domain shape (synthesized from APS tomoscan + 2bm-docs)

A "rotation-axis alignment" is iterative:

  1. Mount the calibration sphere on the kinematic tip.
  2. Rotate to 0°, acquire alignment image, note sphere centroid x.
  3. Rotate to 180°, acquire alignment image, note sphere centroid x.
  4. Compute offset = (centroid_at_180 - centroid_at_0) / 2.
  5. If |offset| > tolerance: adjust SampleTop_X by -offset, goto 2.
  6. Else: write the calibrated rotation-axis pixel position to the
     `RotationCenter` PV. Done.

Convergence typically takes 2-3 iterations starting from a few-pixel
misalignment. The "Check" outcome is the operator's judgment that
sphere centroids match within tolerance; in production this is a
visual call (live tomostream centroid overlay) or an off-line
reconstruction-quality metric (`tomopy.find_center_vo`). Either way,
the success criterion lives outside CORA — CORA records the Check
the operator made + the evidence they cite.

## Asset stack (minimal-but-faithful)

Four target Assets cover the load-bearing instruments:

  - Aerotech ABRS rotary stage (the rotation axis)
  - SampleTop_X linear stage (the X-correction motor; a Kohzu CYAT-070)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (converts X-rays to visible for the camera)

Each gets one Family defined day-one. The hexapod, sample_y,
phantom, and beamline-envelope Assets are deliberately omitted from
the Procedure's target_asset_ids — they're upstream / supporting,
not directly manipulated during the center routine.

## What this test surfaces (gap-finding intent)

See `docs/deployments/2-bm/procedures.md` (the operator-facing
companion) for the gaps documented in domain terms. The most consequential surfaces are:

  - **Iteration loop is first-class**: alignment IS iterative (rotate ->
    check -> adjust -> re-rotate); each pass is bracketed by
    ProcedureIterationStarted / ProcedureIterationEnded, the convergence
    verdict rides on IterationEnded.converged, the count denorms to
    iteration_count, and per-iteration history is queryable via
    proj_operation_procedure_iterations. (This loop previously had no
    first-class shape and was encoded ad-hoc via an `iteration` payload
    key on Check steps; that convention is retired.)
  - **External-tool delegation**: the convergence Check requires
    off-line reconstruction. We model that via `payload.source =
    "operator_visual" | "tomopy_find_center_vo" | "live_tomostream"`
    on Check entries; whether that source-of-truth needs structuring
    is a watch item.
  - **Two-namesake-motor problem** (Tomo@0deg vs Tomo@180deg, same
    physical Asset, two semantic roles): we use the canonical
    `SampleTop_X` name with a `role` payload key on the Setpoint;
    whether AssetPort needs context-dependent identity is a watch
    item.
  - **No discrete success boolean exists in PVs**: the final Check is
    operator judgment + off-line metric. We capture both via the
    polymorphic JSON payload, validating the Path-C trichotomy
    decision.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.calibration._projections import register_calibration_projections
from cora.calibration.aggregates.calibration import (
    CalibrationStatus,
    MeasuredSource,
)
from cora.calibration.features.append_calibration_revision import (
    AppendCalibrationRevision,
)
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import (
    bind as bind_define_calibration,
)
from cora.calibration.quantities import CalibrationQuantity
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.update_asset_settings import (
    UpdateAssetSettings,
)
from cora.equipment.features.update_asset_settings import (
    bind as bind_update_asset_settings,
)
from cora.equipment.features.update_family_settings_schema import (
    UpdateFamilySettingsSchema,
)
from cora.equipment.features.update_family_settings_schema import (
    bind as bind_update_family_settings_schema,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import ProcedureStatus
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import (
    bind as bind_append_step,
)
from cora.operation.features.complete_procedure import (
    CompleteProcedure,
)
from cora.operation.features.complete_procedure import (
    bind as bind_complete,
)
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from cora.operation.features.list_procedure_iterations import bind as bind_list_iterations
from cora.operation.features.list_procedures import (
    ListProcedures,
)
from cora.operation.features.list_procedures import (
    bind as bind_list,
)
from cora.operation.features.register_procedure import (
    RegisterProcedure,
)
from cora.operation.features.register_procedure import (
    bind as bind_register_procedure,
)
from cora.operation.features.start_iteration import StartProcedureIteration
from cora.operation.features.start_iteration import bind as bind_start_iteration
from cora.operation.features.start_procedure import (
    StartProcedure,
)
from cora.operation.features.start_procedure import (
    bind as bind_start,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import (
    DefinePractice,
)
from cora.recipe.features.define_practice import (
    bind as bind_define_practice,
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

_NOW = datetime(2026, 5, 15, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000035bb")

# Pre-allocated id queue. Order matters (FixedIdGenerator consumes head-first).
# Each block annotates which command consumes which IDs. The facility-install
# block (actor + Argonne/APS/Unit + Devices) is consumed by `install_aps_unit`
# via `facility_id_prefix(...)`; everything below is scenario-specific.

# Asset hierarchy: 2-BM (Unit, root) anchored to the self-Facility via
# facility_code. Devices below hang off _2BM_UNIT_ID. Practice's site_id
# references _APS_SITE_ID (an opaque practice-site UUID, NOT an Asset tier).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000350a01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000350501")

# Family ids (4 caps x 2 ids/define = 8)
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Asset ids (4 assets x {2 register + 1 addcap} = 12 ids; we name only the asset ids)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000035a01")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000035a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000035a21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000035a31")

# Recipe ids
_METHOD_ID = UUID("01900000-0000-7000-8000-000000035d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0eae9")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000035d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000035d21")

# Procedure id
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000035e01")

# Steps logbook + open envelope
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000035f01")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000035f02")

# Calibration the alignment produces (define mints calibration_id; append mints revision_id)
_CALIBRATION_ID = UUID("01900000-0000-7000-8000-000000036001")
_CALIBRATION_REVISION_ID = UUID("01900000-0000-7000-8000-000000036002")


_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("SampleTop_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
)


# ----- Family settings_schemas + per-device settings dicts -----
#
# Family.settings_schema declares the intrinsic-property contract for a
# device class (positions, encoder resolution, hardware envelope, per-install
# calibration). Asset.settings carries this specific device's values. Runtime
# parameters (exposure, energy, rotation step) are NOT here -- they belong on
# Method.parameters_schema. Per [[project_pilot_settings_schemas]].
#
# Same-unit-per-physical-dimension-per-Family convention: all RotaryStage
# angle properties in deg; all LinearStage length properties in mm. Different
# physical dimensions in the same Family use different unit codes
# (positions in deg + max_speed in deg/s).

_DRAFT = "https://json-schema.org/draft/2020-12/schema"

_SCHEMA_ROTARY_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "deg"},
        },
        "max_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "deg"},
        },
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "deg"},
        },
        "homing_offset": {
            "type": "number",
            "unit": {"system": "udunits", "code": "deg"},
        },
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

_SCHEMA_LINEAR_STAGE: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "min_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "mm"},
        },
        "max_position": {
            "type": "number",
            "unit": {"system": "udunits", "code": "mm"},
        },
        "max_speed": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm/s"},
        },
        "encoder_resolution": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "mm"},
        },
    },
    "required": ["min_position", "max_position", "max_speed", "encoder_resolution"],
}

_SCHEMA_CAMERA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "sensor_width": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "sensor_height": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "pixel"},
        },
        "pixel_size": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "bit_depth": {
            "type": "integer",
            "minimum": 1,
            "unit": {"system": "udunits", "code": "bit"},
        },
    },
    "required": ["sensor_width", "sensor_height", "pixel_size", "bit_depth"],
}

_SCHEMA_SCINTILLATOR: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "thickness": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "um"},
        },
        "decay_time": {
            "type": "number",
            "minimum": 0,
            "unit": {"system": "udunits", "code": "us"},
        },
    },
    "required": ["thickness", "decay_time"],
}

# Device-specific values (vendor datasheet figures, calibrated per install).

_SETTINGS_AEROTECH_ABRS: dict[str, Any] = {
    "min_position": -360.0,
    "max_position": 360.0,
    "max_speed": 720.0,
    "encoder_resolution": 0.0001,
    "homing_offset": 0.0,
}

_SETTINGS_SAMPLE_TOP_X: dict[str, Any] = {
    "min_position": -10.0,
    "max_position": 10.0,
    "max_speed": 1.0,
    "encoder_resolution": 0.0005,
}

_SETTINGS_ORYX_5MP: dict[str, Any] = {
    "sensor_width": 2448,
    "sensor_height": 2048,
    "pixel_size": 3.45,
    "bit_depth": 12,
}

_SETTINGS_SCINTILLATOR_LUAG: dict[str, Any] = {
    "thickness": 100.0,
    "decay_time": 0.07,
}

_SCHEMA_SPECS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_CAP_ROTARY_STAGE_ID, _SCHEMA_ROTARY_STAGE),
    (_CAP_LINEAR_STAGE_ID, _SCHEMA_LINEAR_STAGE),
    (_CAP_CAMERA_ID, _SCHEMA_CAMERA),
    (_CAP_SCINTILLATOR_ID, _SCHEMA_SCINTILLATOR),
)

_SETTINGS_SPECS: tuple[tuple[UUID, dict[str, Any]], ...] = (
    (_ASSET_AEROTECH_ABRS_ID, _SETTINGS_AEROTECH_ABRS),
    (_ASSET_SAMPLE_TOP_X_ID, _SETTINGS_SAMPLE_TOP_X),
    (_ASSET_ORYX_5MP_ID, _SETTINGS_ORYX_5MP),
    (_ASSET_SCINTILLATOR_LUAG_ID, _SETTINGS_SCINTILLATOR_LUAG),
)


def _id_queue() -> list[UUID]:
    """Build the FixedIdGenerator queue. Anonymous event ids are uuid4()."""
    e = uuid4  # alias for brevity
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # update_family_settings_schema x 4: event_id only
        e(),
        e(),
        e(),
        e(),
        # update_asset_settings x 4: event_id only
        e(),
        e(),
        e(),
        e(),
        # define_method: method_id, event_id
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # start_iteration(1): event_id
        e(),
        # append_activities iter1 (lazy-open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # end_iteration(1): event_id
        e(),
        # start_iteration(2): event_id
        e(),
        # (append_activities iter2 + finalize: no generator ids; logbook already open)
        # end_iteration(2): event_id
        e(),
        # complete_procedure: event_id
        e(),
        # define_calibration: calibration_id, event_id
        _CALIBRATION_ID,
        e(),
        # append_calibration_revision: revision_id, event_id
        _CALIBRATION_REVISION_ID,
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
    """Build a Setpoint step input. `role` carries context-dependent
    semantics (for example, Tomo@0deg vs Tomo@180deg for the same physical
    SampleTop_X motor). `note` is operator's free-text per-step audit."""
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
        event_id=uuid4(),
        step_kind="setpoint",
        payload=payload,
        sampled_at=sampled_at,
    )


def _action(
    *,
    action_name: str,
    sampled_at: datetime,
    **params: Any,
) -> ActivityInput:
    """Build an Action step input. `params` are kind-specific."""
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
    actual: float | None = None,
    expected: float | None = None,
    tolerance: float | None = None,
    source: str = "operator_visual",
    sampled_at: datetime,
    **evidence: Any,
) -> ActivityInput:
    """Build a Check step input. `source` distinguishes operator-visual
    judgment from off-line metrics (for example, tomopy.find_center_vo)."""
    payload: dict[str, Any] = {
        "channel": channel,
        "passed": passed,
        "source": source,
    }
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if tolerance is not None:
        payload["tolerance"] = tolerance
    if evidence:
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
    register_calibration_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_center_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Equipment + Recipe + Operation, run the iterative 0°/180°
    convergence loop, finalize with RotationCenter setpoint, drain the
    projection, assert the operator-readable record is correct.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed facility hierarchy: actor + Argonne -> APS -> 2-BM + Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- declare Family schemas then push per-Asset settings -----
    #
    # Schemas first (4 calls), then values (4 calls). Both are scenario-local
    # rather than baked into install_aps_unit per the design memo
    # anti-hook "DO NOT extract schemas before rule-of-three" -- the shakedown
    # scenario uses the same facility helper without authoring schemas.

    for cap_id, schema in _SCHEMA_SPECS:
        await bind_update_family_settings_schema(deps)(
            UpdateFamilySettingsSchema(family_id=cap_id, settings_schema=schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    for asset_id, settings in _SETTINGS_SPECS:
        await bind_update_asset_settings(deps)(
            UpdateAssetSettings(asset_id=asset_id, settings_patch=settings),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Seed Recipe BC: Method + Practice + Plan describing the alignment recipe -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.alignment",
        name="Alignment",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="center_alignment",
            needed_family_ids=frozenset(
                {
                    _CAP_ROTARY_STAGE_ID,
                    _CAP_LINEAR_STAGE_ID,
                    _CAP_CAMERA_ID,
                    _CAP_SCINTILLATOR_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(name="2BM_alignment_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_center_routine_plan",
            practice_id=_PRACTICE_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
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
            name="2-BM rotation-axis alignment (vessel-A bakeout pre-scan)",
            kind="center_alignment",
            target_asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
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

    # ----- Append the alignment step sequence (one full convergence) -----

    # Step timestamps walk forward by 1 second each, like real operator gestures.
    def t(seconds: int) -> datetime:
        return datetime(2026, 5, 15, 14, 0, seconds, tzinfo=UTC)

    # Iteration 1: large initial offset. Convergence fails.
    iter1_steps = (
        _setpoint(
            channel="Tomo_Rot",
            target_value=0.0,
            units="deg",
            note="initial 0deg reference",
            sampled_at=t(1),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter1_0deg.h5",
            sampled_at=t(2),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=True,
            actual=1024.0,
            expected=1024.0,
            tolerance=5.0,
            source="live_tomostream_centroid",
            sampled_at=t(3),
        ),
        _setpoint(
            channel="Tomo_Rot",
            target_value=180.0,
            units="deg",
            note="180deg counterpart",
            sampled_at=t(4),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter1_180deg.h5",
            sampled_at=t(5),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=False,
            actual=1031.0,
            expected=1024.0,
            tolerance=1.0,
            source="live_tomostream_centroid",
            offset_px=7.0,
            sampled_at=t(6),
        ),
        # Correction: offset_px / 2 = 3.5 px. Pixel size ~1 um per px (typical 5x lens),
        # so correction is ~3.5 um in motor units. Operator chooses the sign by convention.
        _setpoint(
            channel="SampleTop_X",
            target_value=-3.5,
            units="um",
            role="Tomo@180deg",
            note="X-correction for iteration 1 offset; convention: -offset_px / 2",
            sampled_at=t(7),
        ),
    )

    # Iteration 2: converges within tolerance.
    iter2_steps = (
        _setpoint(
            channel="Tomo_Rot",
            target_value=0.0,
            units="deg",
            note="post-correction 0deg reference",
            sampled_at=t(8),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter2_0deg.h5",
            sampled_at=t(9),
        ),
        _setpoint(
            channel="Tomo_Rot",
            target_value=180.0,
            units="deg",
            note="180deg post-correction",
            sampled_at=t(10),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter2_180deg.h5",
            sampled_at=t(11),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=True,
            actual=1024.5,
            expected=1024.0,
            tolerance=1.0,
            source="live_tomostream_centroid",
            offset_px=0.5,
            sampled_at=t(12),
        ),
    )

    # Finalize: write the calibrated rotation-axis pixel position to the PV
    # consumed by downstream science scans.
    finalize_step = _setpoint(
        channel="RotationCenter",
        target_value=1024.5,
        units="px",
        note="calibrated rotation-axis pixel position for 2-BM micro-CT",
        sampled_at=t(13),
    )

    # Each convergence pass is bracketed by start_iteration / end_iteration:
    # iteration is first-class now, so the count + verdict live on the
    # boundary events, not on an `evidence['iteration']` payload key.
    step_store = _postgres_step_store(db_pool)

    # Iteration 1: large initial offset; does not converge.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count1 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter1_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count1 == 7
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=1,
            converged=False,
            reason="sphere centroid offset 7.0px exceeds 1.0px tolerance",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Iteration 2: converges within tolerance.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count2 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter2_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count2 == 5
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=2,
            converged=True,
            reason=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Finalize (post-convergence, outside the iteration loop): write the
    # calibrated rotation-axis pixel position to the PV downstream scans read.
    count_final = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=(finalize_step,)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count_final == 1

    # ----- Complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Emit the rotation-center Calibration the alignment produced -----
    #
    # The alignment Procedure is the ACT; the Calibration BC stores the RESULT.
    # The caller bridges them: after the procedure completes, define the
    # rotation_center Calibration for the rotary stage and append a Provisional
    # revision sourced from this Procedure (MeasuredSource). This is the
    # human/caller-driven path; an automatic ProcedureCompleted agent that drafts
    # the revision is a deferred tier (see the Calibration module Out-of-scope).

    calibration_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=_ASSET_AEROTECH_ABRS_ID,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point={"energy": 25.0, "optics_config": "5x"},
            description="Rotation centre from the 2-BM center-alignment routine.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert calibration_id == _CALIBRATION_ID
    revision_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=calibration_id,
            value={"center": 1024.5, "uncertainty": 0.5},
            status=CalibrationStatus.PROVISIONAL,
            source=MeasuredSource(procedure_id=_PROCEDURE_ID),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert revision_id == _CALIBRATION_REVISION_ID

    # The Calibration stream proves the act -> result link: the appended revision
    # cites this alignment Procedure as its MeasuredSource, Provisional until blessed.
    calibration_events, _ = await deps.event_store.load("Calibration", _CALIBRATION_ID)
    assert [e.event_type for e in calibration_events] == [
        "CalibrationDefined",
        "CalibrationRevisionAppended",
    ]
    appended = calibration_events[1].payload
    assert appended["status"] == "Provisional"
    assert appended["source_procedure_id"] == str(_PROCEDURE_ID)
    assert appended["value"] == {"center": 1024.5, "uncertainty": 0.5}

    # ----- Assert the Procedure stream tells the right lifecycle story -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    # The iteration boundary pair now interleaves with the lifecycle: the
    # logbook opens on the first append (inside iteration 1), so the order is
    # Registered, Started, IterationStarted(1), ActivitiesLogbookOpened,
    # IterationEnded(1), IterationStarted(2), IterationEnded(2), Completed.
    assert procedure_version == 8, f"expected 8 events on Procedure stream, got {procedure_version}"
    procedure_event_types = [e.event_type for e in procedure_events]
    assert procedure_event_types == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureIterationStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureCompleted",
    ]

    # ----- Assert the per-step logbook table has all 13 entries with the right kinds -----

    step_rows = await _read_steps(db_pool, _PROCEDURE_ID)
    assert len(step_rows) == 13
    kinds_in_order = [r["step_kind"] for r in step_rows]
    expected_kinds = [
        # iteration 1
        "setpoint",
        "action",
        "check",
        "setpoint",
        "action",
        "check",
        "setpoint",
        # iteration 2
        "setpoint",
        "action",
        "setpoint",
        "action",
        "check",
        # finalize
        "setpoint",
    ]
    assert kinds_in_order == expected_kinds

    # The final setpoint records the calibrated rotation-axis pixel position --
    # the artifact a downstream science scan will read.
    final_setpoint_payload = json.loads(step_rows[-1]["payload"])
    assert final_setpoint_payload["channel"] == "RotationCenter"
    assert final_setpoint_payload["target_value"] == 1024.5
    assert final_setpoint_payload["units"] == "px"

    # The convergence Check (iteration 2's last check) records the operator's
    # judgment + supporting evidence. Iteration is no longer encoded here
    # (no `evidence['iteration']`); it is first-class, asserted via the
    # per-iteration read model below.
    convergence_check_payload = json.loads(step_rows[11]["payload"])
    assert convergence_check_payload["passed"] is True
    assert convergence_check_payload["source"] == "live_tomostream_centroid"
    assert convergence_check_payload["evidence"]["offset_px"] == 0.5
    assert "iteration" not in convergence_check_payload["evidence"]

    # ----- Drain the projection and assert the read-side record is operator-correct -----

    await _drain(db_pool)

    # The Calibration read-side renders the measured source for the rotation centre.
    async with db_pool.acquire() as conn:
        cal_row = await conn.fetchrow(
            "SELECT latest_revision_status, latest_revision_source_kind "
            "FROM proj_calibration_summary WHERE calibration_id = $1",
            _CALIBRATION_ID,
        )
    assert cal_row is not None
    assert cal_row["latest_revision_status"] == "Provisional"
    assert cal_row["latest_revision_source_kind"] == "measured"

    page = await bind_list(deps)(
        ListProcedures(kind="center_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    proc_summary = matching[0]
    assert proc_summary.name == "2-BM rotation-axis alignment (vessel-A bakeout pre-scan)"
    assert proc_summary.kind == "center_alignment"
    assert proc_summary.status == ProcedureStatus.COMPLETED.value
    assert proc_summary.activity_logbook_id == _STEPS_LOGBOOK_ID
    # All 4 target Assets surface in the read model for at-a-glance ops queries.
    assert set(proc_summary.target_asset_ids) == {
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    }
    assert proc_summary.parent_run_id is None  # standalone alignment, not Phase-of-Run
    assert proc_summary.last_status_changed_at == _NOW
    # Iteration is first-class: the count denorms onto the summary.
    assert proc_summary.iteration_count == 2

    # ----- Per-iteration convergence read model: which passes converged -----
    iterations = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert [i.iteration_index for i in iterations.items] == [1, 2]
    assert iterations.items[0].converged is False  # iteration 1 missed
    assert iterations.items[0].reason == "sphere centroid offset 7.0px exceeds 1.0px tolerance"
    assert iterations.items[1].converged is True  # iteration 2 converged

    # ----- Reverse-direction filter: the target_asset_id GIN index works for
    #       "show me all procedures touching the Aerotech rotary stage" -----
    page_by_asset = await bind_list(deps)(
        ListProcedures(target_asset_id=_ASSET_AEROTECH_ABRS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert any(item.procedure_id == _PROCEDURE_ID for item in page_by_asset.items)

    # ----- assert Family schemas + Asset settings landed -----
    #
    # Schemas + settings are NOT in proj_equipment_family_summary or
    # proj_equipment_asset_summary by design (5g-a / 5g-c locks: no list-by-
    # settings-key consumer yet). Verify via event-stream replay instead.

    for cap_id, expected_schema in _SCHEMA_SPECS:
        events, version = await deps.event_store.load("Family", cap_id)
        assert version == 2, (
            f"Family {cap_id} should have 2 events (Defined + SchemaUpdated); got {version}"
        )
        event_types = [e.event_type for e in events]
        assert event_types == ["FamilyDefined", "FamilySettingsSchemaUpdated"]
        assert events[1].payload["settings_schema"] == expected_schema

    for asset_id, expected_settings in _SETTINGS_SPECS:
        events, version = await deps.event_store.load("Asset", asset_id)
        # Expected sequence: Registered, FamilyAdded, SettingsUpdated.
        assert version == 3, (
            f"Asset {asset_id} should have 3 events "
            f"(Registered + FamilyAdded + SettingsUpdated); got {version}"
        )
        event_types = [e.event_type for e in events]
        assert event_types == [
            "AssetRegistered",
            "AssetFamilyAdded",
            "AssetSettingsUpdated",
        ]
        # 5g-c: event payload carries the FULL post-merge dict.
        assert events[-1].payload["settings"] == expected_settings


# ---------------- Helpers ----------------


def _postgres_step_store(db_pool: asyncpg.Pool):
    """Build a PostgresActivityStore for the BC-internal step writer.

    `wire_operation` constructs this normally from `deps.pool`; the
    scenario test exercises the slice handler directly via `bind_append`,
    so we construct the store here.
    """
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT step_kind, payload, sampled_at
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1
            ORDER BY sampled_at
            """,
            procedure_id,
        )
