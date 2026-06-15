"""Focus alignment at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the `focus` step of the rotation-axis alignment
chain. Adjusts the sample-to-scintillator distance via the
`SampleTop_Z` linear stage until the image's depth-of-focus peaks
for the mounted sample. Comes second in the five-routine chain
(`resolution -> focus -> center -> roll -> pitch`); resolution
must converge first so the microscope optics are at peak sharpness
before adjusting the sample-Z axis.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

To ground the `focus_alignment` Procedure inventory row on
`docs/deployments/2-bm/procedures.md`, and to register a new Asset
(`SampleTop_Z`) that no prior scenario has touched. Per
[[project_pilot_docs_design]] no doc page may name an aggregate until
a scenario test registers it; this file unlocks the Z-axis sample
stage in the 2-BM Asset inventory.

## Distinction from `resolution_alignment`

Both routines optimize image sharpness, but on different motors:

  - `resolution_alignment` adjusts the **microscope internal focus**
    (`Focus`, lens-to-scintillator distance, small
    range, sub-micron resolution).
  - `focus_alignment` adjusts the **sample-to-scintillator distance**
    (`SampleTop_Z`, cm-range linear stage, ~10um resolution).
    Affects magnification + depth-of-focus together.

In the operator chain order, resolution runs first to fix the
microscope's intrinsic sharpness, then focus tunes the sample
position within that sharpened optical path.

## Domain shape (synthesized from APS imaging-group practice)

Iterative peak-search on a 1D sharpness curve, mechanically similar
to resolution alignment but on a different motor with a wider
step size:

  1. Mount the sample (or focus phantom) on the kinematic tip.
  2. Set `SampleTop_Z` to nominal position, acquire, measure
     sharpness.
  3. Step Z by +/-0.5mm, acquire, measure. Bracket the peak.
  4. Bisect within the bracket, acquire, measure.
  5. Lock Z at the peak.

Typical convergence: 3-4 acquisitions starting within +/-1mm of the
true peak. Step size is ~10x larger than resolution_alignment because
the sample-Z range is wider and the sharpness curve broader.

## Asset stack (Z motor + detector chain)

  - SampleTop_Z linear stage (the sample-to-scintillator distance
    motor; cm range, ~10um resolution)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (visible-light conversion)

Rotation stage, X-correction motor, and Optique Peter focus-Z are
omitted: this routine does not manipulate them. They participate in
the downstream `center` / `roll` / `pitch` routines and the
upstream `resolution` routine respectively.

## What this scenario surfaces (gap-finding intent)

  - **Iteration loop is first-class**: the peak-search IS iterative
    (step -> measure -> bracket -> bisect); each pass is bracketed by
    ProcedureIterationStarted / ProcedureIterationEnded, the convergence
    verdict rides on IterationEnded.converged, the count denorms to
    iteration_count, and per-iteration history is queryable via
    proj_operation_procedure_iterations. (This loop previously had no
    first-class shape and was encoded ad-hoc via the Setpoint `role` /
    Check `direction` payload keys; that convention is retired as the
    source of iteration truth.)
  - **Magnification couples with focus on this axis.** Moving
    SampleTop_Z changes both depth-of-focus AND projection
    magnification. The sharpness Check captures the focus quality,
    but the corresponding magnification shift is implicit in the
    sample-Z value and must be accounted for in downstream
    reconstruction. Whether magnification should be its own
    first-class Check entry is a watch item.
  - **Sample-Z mount tolerance.** Long Z moves can shift the sample
    laterally in X / Y due to mounting compliance, falsifying the
    sharpness measurement. The scenario does not encode this; a
    real procedure may interleave Y / X re-centering after large
    Z moves. Whether the focus routine should require a mount-
    rigidity Check is a watch item.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.end_iteration import EndProcedureIteration
from cora.operation.features.end_iteration import bind as bind_end_iteration
from cora.operation.features.list_procedure_iterations import ListProcedureIterations
from cora.operation.features.list_procedure_iterations import bind as bind_list_iterations
from cora.operation.features.list_procedures import ListProcedures
from cora.operation.features.list_procedures import bind as bind_list
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_iteration import StartProcedureIteration
from cora.operation.features.start_iteration import bind as bind_start_iteration
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

_NOW = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000356bb")

# Facility hierarchy + operator Actor (Actor.id == _PRINCIPAL_ID)
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000356a01")
# Practice site_id: an opaque practice-site UUID (NOT an Asset tier).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000356501")

# Capabilities (sample-Z motor needs LinearStage + the drive electronics
# behind it needs MotionController; image chain needs Camera + Scintillator)
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_MOTION_CONTROLLER_OMS_2BMB_ID = family_stream_id(FamilyName("MotionController"))

# Devices (sample-Z motor + image chain + the OMS-VME58 drive electronics
# behind SampleTop_Z; the OMS-VME58 in the 2-BM b-station IOC crate
# `ioc2bmb` drives SampleTop_Z on channel `2bmb:m17`; this is the fourth
# MotionController Asset shipped at 2-BM per
# [[project-controller-as-asset-stage1-design]]. Image chain Assets
# (camera + scintillator) carry no controller_id; their drivers are
# passive on this slice.
_ASSET_OMS_VME58_2BMB_DRIVE_ID = UUID("01900000-0000-7000-8000-000000356a41")
_ASSET_SAMPLE_TOP_Z_ID = UUID("01900000-0000-7000-8000-000000356a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000356a21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000356a31")

# Recipe ladder
_METHOD_FOCUS_ID = UUID("01900000-0000-7000-8000-000000356d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ea89")
_PRACTICE_FOCUS_ID = UUID("01900000-0000-7000-8000-000000356d11")
_PLAN_FOCUS_ID = UUID("01900000-0000-7000-8000-000000356d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000356f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000356f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000356f12")


_DEVICES = (
    # Controller comes first: register_asset for the OMS-VME58 must land
    # before SampleTop_Z's register_asset (which carries
    # `controller_id=_ASSET_OMS_VME58_2BMB_DRIVE_ID`). Decider does not
    # validate the reference exists (eventual-consistency stance from
    # the rotary anchor), but dependency-order registration matches
    # real-world ceremony.
    DeviceSpec(
        "SampleStageDrive",
        _ASSET_OMS_VME58_2BMB_DRIVE_ID,
        "MotionController",
        _CAP_MOTION_CONTROLLER_OMS_2BMB_ID,
    ),
    DeviceSpec(
        "SampleTop_Z",
        _ASSET_SAMPLE_TOP_Z_ID,
        "LinearStage",
        _CAP_LINEAR_STAGE_ID,
        controller_id=_ASSET_OMS_VME58_2BMB_DRIVE_ID,
    ),
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
        # activate_asset x 3: event_id only (no aggregate id allocated)
        e(),
        e(),
        e(),
        # define_method: method_id, event_id
        _METHOD_FOCUS_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_FOCUS_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_FOCUS_ID,
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
        # end_iteration(2): event_id
        e(),
        # start_iteration(3): event_id
        e(),
        # end_iteration(3): event_id
        e(),
        # start_iteration(4): event_id
        e(),
        # (append_activities iter4 + finalize: no generator ids; logbook already open)
        # end_iteration(4): event_id
        e(),
        # complete_procedure: event_id
        e(),
    ]


def _setpoint(
    *,
    target_mm: float,
    role: str,
    sampled_at: datetime,
    note: str | None = None,
) -> ActivityInput:
    """Build a SampleTop_Z Setpoint step input."""
    payload: dict[str, Any] = {
        "channel": "SampleTop_Z",
        "target_value": target_mm,
        "units": "mm",
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
    """Build an Action step for acquiring an alignment frame."""
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_alignment_frame",
            "params": {"exposure_ms": exposure_ms},
        },
        sampled_at=sampled_at,
    )


def _sharpness_check(
    *,
    value: float,
    sample: str,
    sampled_at: datetime,
    passed: bool = False,
    direction: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ActivityInput:
    """Build a Check step for image-analysis sharpness.

    `sample` records what was mounted (focus phantom, the user's
    actual sample class, etc.); `direction` records the measurement
    delta vs the prior iteration."""
    payload: dict[str, Any] = {
        "channel": "image_sharpness",
        "passed": passed,
        "source": "tomopy.misc.morph",
        "actual": value,
        "sample": sample,
    }
    if direction is not None:
        payload["direction"] = direction
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
async def test_focus_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + 3 Assets (SampleTop_Z + image chain), run an
    iterative depth-of-focus search on a focus phantom, assert the
    auditable record carries 4 iterations bracketing the peak plus
    one final lock setpoint at the converged Z position."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Install the 2-BM facility hierarchy + the 3 Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: activate all 3 Devices (Commissioned -> Active) -----

    for asset_id in (_ASSET_SAMPLE_TOP_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: Method + Practice + Plan for the focus routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.alignment",
        name="Alignment",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="focus_alignment",
            needed_family_ids=frozenset(
                {_CAP_LINEAR_STAGE_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_focus_practice",
            method_id=_METHOD_FOCUS_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_focus_plan",
            practice_id=_PRACTICE_FOCUS_ID,
            asset_ids=frozenset(
                {_ASSET_SAMPLE_TOP_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM focus alignment (depth-of-focus phantom)",
            kind="focus_alignment",
            target_asset_ids=frozenset(
                {_ASSET_SAMPLE_TOP_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
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

    # ----- Procedure step entries: 4-iteration peak-bracket search on SampleTop_Z -----
    #
    # Wider step than resolution_alignment (0.5mm vs 50um) because the
    # sample-Z motor range is centimeters and the sharpness curve is
    # broader.

    t = _NOW
    sample = "depth_phantom"
    iter1 = (
        _setpoint(
            target_mm=0.000, role="initial", sampled_at=t, note="user-supplied start position"
        ),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(value=0.50, sample=sample, sampled_at=t),
    )
    iter2 = (
        _setpoint(target_mm=0.500, role="step_positive", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(value=0.70, sample=sample, sampled_at=t, direction="better"),
    )
    iter3 = (
        _setpoint(target_mm=1.000, role="step_positive", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(
            value=0.65,
            sample=sample,
            sampled_at=t,
            direction="worse",
            evidence={"bracket_low_mm": 0.500, "bracket_high_mm": 1.000},
        ),
    )
    iter4 = (
        _setpoint(target_mm=0.750, role="bisect", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(
            value=0.74,
            sample=sample,
            sampled_at=t,
            passed=True,
            direction="peak",
            evidence={"peak_position_mm": 0.750},
        ),
    )
    finalize = (_setpoint(target_mm=0.750, role="lock_at_peak", sampled_at=t),)

    # Each peak-search pass is bracketed by start_iteration / end_iteration:
    # iteration is first-class now, so the count + convergence verdict live on
    # the boundary events, not on the Setpoint `role` / Check `direction` keys.
    step_store = _postgres_step_store(db_pool)

    # Iteration 1: initial position; no bracket yet, does not converge.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count1 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count1 == 3
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=1,
            converged=False,
            reason="initial sharpness 0.50; peak not yet bracketed",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Iteration 2: step +0.5mm; sharpness improves but peak not bracketed.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count2 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count2 == 3
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=2,
            converged=False,
            reason="sharpness improving (0.70); peak not yet bracketed",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Iteration 3: step +1.0mm; sharpness drops, peak now bracketed in [0.5, 1.0]mm.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=3),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count3 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter3),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count3 == 3
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=3,
            converged=False,
            reason="sharpness dropped to 0.65; peak bracketed in [0.500, 1.000]mm",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Iteration 4: bisect at 0.75mm; sharpness peaks, converged.
    await bind_start_iteration(deps)(
        StartProcedureIteration(procedure_id=_PROCEDURE_ID, iteration_index=4),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    count4 = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=iter4),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count4 == 3
    await bind_end_iteration(deps)(
        EndProcedureIteration(
            procedure_id=_PROCEDURE_ID,
            iteration_index=4,
            converged=True,
            reason=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Finalize (post-convergence, outside the iteration loop): lock SampleTop_Z
    # at the peak position for the downstream science scan.
    count_final = await bind_append_step(deps, step_store=step_store)(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=finalize),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count_final == 1

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Procedure stream lifecycle (12 events) -----
    #
    # The iteration boundary pairs now interleave with the lifecycle: the
    # logbook opens on the first append (inside iteration 1), so the order is
    # Registered, Started, IterationStarted(1), ActivitiesLogbookOpened,
    # IterationEnded(1), then (IterationStarted, IterationEnded) x 3, Completed.
    # version = 4 (Registered + Started + LogbookOpened + Completed) + 2 per
    # iteration = 4 + 2*4 = 12.

    events, version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert version == 12
    assert [e.event_type for e in events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureIterationStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureIterationStarted",
        "ProcedureIterationEnded",
        "ProcedureCompleted",
    ]

    # ----- Assert: each target Asset reached Active lifecycle -----

    for asset_id in (_ASSET_SAMPLE_TOP_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        asset_events, _ = await deps.event_store.load("Asset", asset_id)
        event_types = [e.event_type for e in asset_events]
        assert event_types == ["AssetRegistered", "AssetFamilyAdded", "AssetActivated"]

    # ----- Assert: OMS-VME58 2bmb controller stream landed (Commissioned-only) -----

    controller_events, _ = await deps.event_store.load("Asset", _ASSET_OMS_VME58_2BMB_DRIVE_ID)
    assert [e.event_type for e in controller_events] == [
        "AssetRegistered",  # genesis (Commissioned; not Activated this scenario)
        "AssetFamilyAdded",  # +MotionController
    ]
    # Controller-is-leaf rule: the VME crate carries no controller_id
    # back-reference of its own. Omit-when-None wire shape.
    assert "controller_id" not in controller_events[0].payload

    # ----- Assert: SampleTop_Z's AssetRegistered payload carries controller_id -----

    # SampleTop_Z is driven by the OMS-VME58 in `ioc2bmb` on channel
    # `2bmb:m17`; the controller_id back-reference is the addressability
    # handle that lets controller-scoped Cautions (e.g. a VME-bus glitch
    # on the OMS box) surface against Plans that target the stage only,
    # via the start_run scope-expansion shipped in commit cb50a69de.
    sample_z_events, _ = await deps.event_store.load("Asset", _ASSET_SAMPLE_TOP_Z_ID)
    sample_z_registered_payload = sample_z_events[0].payload
    assert UUID(sample_z_registered_payload["controller_id"]) == _ASSET_OMS_VME58_2BMB_DRIVE_ID

    # ----- Assert: 13 step entries land in the projection in canonical order -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 13
    assert [r["step_kind"] for r in rows] == [
        "setpoint",
        "action",
        "check",  # iteration 1 (initial)
        "setpoint",
        "action",
        "check",  # iteration 2 (step_positive, better)
        "setpoint",
        "action",
        "check",  # iteration 3 (step_positive, worse, bracket)
        "setpoint",
        "action",
        "check",  # iteration 4 (bisect, peak)
        "setpoint",  # finalize (lock_at_peak)
    ]

    # ----- Assert: iteration is first-class on the summary + per-iteration read -----
    #
    # The convergence loop is no longer encoded ad-hoc via the Setpoint `role`
    # / Check `direction` payload keys; it lives on the boundary events. The
    # count denorms to the summary, and the per-iteration verdicts are queryable.

    page = await bind_list(deps)(
        ListProcedures(kind="focus_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    assert matching[0].iteration_count == 4

    iterations = await bind_list_iterations(deps)(
        ListProcedureIterations(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert [i.iteration_index for i in iterations.items] == [1, 2, 3, 4]
    assert [i.converged for i in iterations.items] == [False, False, False, True]
    assert iterations.items[3].reason is None  # the converged pass carries no reason
