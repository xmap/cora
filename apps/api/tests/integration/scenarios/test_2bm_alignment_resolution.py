"""Resolution alignment at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the `resolution` step of the rotation-axis alignment
chain. Adjusts the Optique Peter focus-Z motor on a mounted resolution
target (Siemens star) until the image sharpness metric peaks. Comes
first in the five-routine chain (`resolution -> focus -> center ->
roll -> pitch`); without it, downstream routines run on defocused
frames and produce meaningless calibrated values.

See [[project_pilot_docs_design]] for the phase / file-naming taxonomy
this scenario fits into.

## Why this scenario exists

To ground the `resolution_alignment` Procedure inventory row on
`docs/deployments/2-bm/procedures.md`, and to register a new Asset
(`Focus`) that no prior scenario has touched. Per
[[project_pilot_docs_design]] no doc page may name an aggregate until
a scenario test registers it; this file unlocks the focus-Z motor in
the 2-BM Asset inventory.

## Domain shape (synthesized from APS imaging-group practice)

Iterative peak-search on a 1D sharpness curve:

  1. Mount a resolution target (Siemens star, USAF 1951, or grating) on
     the kinematic tip.
  2. Set focus-Z to an initial position, acquire a frame, measure
     sharpness via image-analysis (`tomopy.misc.morph` or per-beamline
     equivalent).
  3. Step focus-Z in one direction (typically +50um), acquire,
     measure. If sharper, continue; if worse, the peak is bracketed.
  4. Bisect within the bracket, acquire, measure. Repeat until the
     sharpness improvement per step falls under tolerance.
  5. Lock focus-Z at the peak.

Typical convergence: 3-4 acquisitions starting within +/- 100um of the
true peak. Sharpness scale is target-dependent; absolute values are
not comparable across resolution targets, only across iterations of
the same target.

## Asset stack (focus motor + detector chain)

  - Optique Peter focus-Z motor (the lens-to-scintillator distance
    knob; small range, sub-micron resolution)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (visible-light conversion)

Rotation stage and X-correction motor are deliberately omitted from
the Procedure's `target_asset_ids`: they're not directly manipulated
during resolution; they participate in the downstream `center` and
`roll` / `pitch` routines.

## What this scenario surfaces (gap-finding intent)

  - **Sharpness metric is target-dependent.** A `target` payload key on
    Check entries records which resolution target was mounted; absolute
    values are not comparable across `target` values. Whether the
    Subject BC should model the resolution target (vs. operator
    tribal knowledge) is a watch item.
  - **Bisection vs step-and-search vs golden-section.** The operator
    chose bisection here; the choice is captured via `role` on Setpoint
    entries (`step_positive`, `bisect`, `lock_at_peak`). Whether the
    search strategy should be a first-class field is a watch item.
  - **Peak detection is operator judgment.** The final Check carries
    `passed=True` when the operator decides the sharpness curve has
    peaked; there is no enforced numerical convergence criterion.
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

_NOW = datetime(2026, 5, 17, 10, 15, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000355bb")

# Facility hierarchy + operator Actor (Actor.id == _PRINCIPAL_ID)
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000355501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000355a01")

# Capabilities (focus motor needs LinearStage; image chain needs Camera +
# Scintillator; the focus motor's drive electronics is a separate
# MotionController Asset per [[project-controller-as-asset-stage1-design]])
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_MOTION_CONTROLLER_ID = family_stream_id(FamilyName("MotionController"))

# Devices: the focus motor's controller (FocusDrive) is
# registered FIRST so Focus's controller_id back-
# reference targets an already-registered Asset stream. Image chain
# (camera + scintillator) is passive and carries no controller_id.
# FocusDrive is the THIRD MotionController Asset shipped
# at 2-BM (rotary + hexapod first); the drive's specific product line
# is not named on the 2-BM source page (operators address it via the
# IOC handle `2bmbAERO`; the drive itself is almost certainly Aerotech
# Ensemble-family but unconfirmed), so the Asset name uses the IOC
# handle and settings carry `unknown-pending-confirmation` placeholders
# per the intentional-modeling rule.
_ASSET_AEROTECH_2BMBAERO_DRIVE_ID = UUID("01900000-0000-7000-8000-000000355a41")
_ASSET_FOCUS_Z_ID = UUID("01900000-0000-7000-8000-000000355a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000355a21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000355a31")

# Recipe ladder
_METHOD_RESOLUTION_ID = UUID("01900000-0000-7000-8000-000000355d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e8cf")
_PRACTICE_RESOLUTION_ID = UUID("01900000-0000-7000-8000-000000355d11")
_PLAN_RESOLUTION_ID = UUID("01900000-0000-7000-8000-000000355d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000355f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000355f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000355f12")


_DEVICES = (
    DeviceSpec(
        "FocusDrive",
        _ASSET_AEROTECH_2BMBAERO_DRIVE_ID,
        "MotionController",
        _CAP_MOTION_CONTROLLER_ID,
    ),
    DeviceSpec(
        "Focus",
        _ASSET_FOCUS_Z_ID,
        "LinearStage",
        _CAP_LINEAR_STAGE_ID,
        controller_id=_ASSET_AEROTECH_2BMBAERO_DRIVE_ID,
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
        _METHOD_RESOLUTION_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_RESOLUTION_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_RESOLUTION_ID,
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
    target_mm: float,
    role: str,
    sampled_at: datetime,
    note: str | None = None,
) -> ActivityInput:
    """Build a focus-Z Setpoint step input. `role` distinguishes
    initial position, search steps, bisection, and final lock."""
    payload: dict[str, Any] = {
        "channel": "Focus",
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
    target: str,
    sampled_at: datetime,
    passed: bool = False,
    direction: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ActivityInput:
    """Build a Check step for an image-analysis sharpness metric.

    `target` records which resolution target was mounted (for example,
    "siemens_star", "usaf_1951"); `direction` records whether the
    measurement was better / worse / bracketing relative to the prior
    iteration; `evidence` carries free-form structured context (such
    as bracket bounds during bisection)."""
    payload: dict[str, Any] = {
        "channel": "image_sharpness",
        "passed": passed,
        "source": "tomopy.misc.morph",
        "actual": value,
        "target": target,
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
async def test_resolution_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + focus-Z motor + image chain + the focus motor's
    drive-electronics controller (`FocusDrive`, the third
    MotionController Asset shipped at 2-BM per the controller-as-Asset
    design). Run an iterative focus-peak search Procedure on a
    Siemens-star resolution target. Assert the auditable record carries
    4 iterations bracketing the peak plus one final lock setpoint, AND
    that the focus motor's `controller_id` back-reference targets the
    controller Asset stream that the install ceremony registered."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Install the 2-BM facility hierarchy (Argonne -> APS -> Unit) + the 3 Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: activate all 3 Devices (Commissioned -> Active) -----

    for asset_id in (_ASSET_FOCUS_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: Method + Practice + Plan for the resolution routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.alignment",
        name="Alignment",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="resolution_alignment",
            needed_family_ids=frozenset(
                {_CAP_LINEAR_STAGE_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_resolution_practice",
            method_id=_METHOD_RESOLUTION_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_resolution_plan",
            practice_id=_PRACTICE_RESOLUTION_ID,
            asset_ids=frozenset(
                {_ASSET_FOCUS_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM resolution alignment (Siemens-star target)",
            kind="resolution_alignment",
            target_asset_ids=frozenset(
                {_ASSET_FOCUS_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
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

    # ----- Procedure step entries: 4-iteration peak-bracket search -----
    #
    # The operator brackets the focus-Z peak with two outward steps from
    # the initial position, then bisects to land within tolerance of the
    # peak. Final Setpoint locks the focus at the peak.

    t = _NOW
    target = "siemens_star"
    iter1 = (
        _setpoint(
            target_mm=0.000, role="initial", sampled_at=t, note="user-supplied start position"
        ),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(value=0.62, target=target, sampled_at=t),
    )
    iter2 = (
        _setpoint(target_mm=0.050, role="step_positive", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(value=0.78, target=target, sampled_at=t, direction="better"),
    )
    iter3 = (
        _setpoint(target_mm=0.100, role="step_positive", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(
            value=0.71,
            target=target,
            sampled_at=t,
            direction="worse",
            evidence={"bracket_low_mm": 0.050, "bracket_high_mm": 0.100},
        ),
    )
    iter4 = (
        _setpoint(target_mm=0.075, role="bisect", sampled_at=t),
        _acquire(exposure_ms=200, sampled_at=t),
        _sharpness_check(
            value=0.82,
            target=target,
            sampled_at=t,
            passed=True,
            direction="peak",
            evidence={"peak_position_mm": 0.075},
        ),
    )
    finalize = (_setpoint(target_mm=0.075, role="lock_at_peak", sampled_at=t),)

    all_entries = iter1 + iter2 + iter3 + iter4 + finalize
    assert len(all_entries) == 13, "expected 13 entries for a 4-iteration converged search"

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=all_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 13

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

    # ----- Assert: each of the 3 target Assets ended in Active lifecycle -----

    for asset_id in (_ASSET_FOCUS_Z_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        asset_events, _ = await deps.event_store.load("Asset", asset_id)
        event_types = [e.event_type for e in asset_events]
        assert event_types == ["AssetRegistered", "AssetFamilyAdded", "AssetActivated"]

    # ----- Assert: FocusDrive controller stream landed -----
    # Controller stays Commissioned (not activated): controllers are the
    # leaf of the drive-electronics chain at v1, and activation is a
    # stage-side ceremony. Same shape as the rotary anchor's
    # RotaryDrive and the hexapod's HexapodDrive.

    controller_events, _ = await deps.event_store.load("Asset", _ASSET_AEROTECH_2BMBAERO_DRIVE_ID)
    assert [e.event_type for e in controller_events] == [
        "AssetRegistered",  # genesis (Commissioned)
        "AssetFamilyAdded",  # +MotionController
    ]
    # The controller carries no controller_id back-reference of its own.
    # Omit-when-None wire shape: key absent rather than serialized as null.
    assert "controller_id" not in controller_events[0].payload

    # ----- Assert: focus_Z's AssetRegistered carries the controller_id back-reference -----

    focus_z_events, _ = await deps.event_store.load("Asset", _ASSET_FOCUS_Z_ID)
    focus_z_registered_payload = focus_z_events[0].payload
    assert UUID(focus_z_registered_payload["controller_id"]) == _ASSET_AEROTECH_2BMBAERO_DRIVE_ID

    # ----- Assert: passive image-chain Assets omit controller_id (no modelled drive) -----

    for passive_asset_id in (_ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        passive_events, _ = await deps.event_store.load("Asset", passive_asset_id)
        assert "controller_id" not in passive_events[0].payload

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
