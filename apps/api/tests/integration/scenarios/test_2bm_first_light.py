"""First light at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Equipment, Operation, Recipe

Scenario test for the canonical commissioning milestone: the first
time beam passes through the 2-BM optics chain, hits the LuAG
scintillator, and shows up on the Oryx camera. Opens with a dark
frame (shutter closed) to verify the imaging chain is electronically
quiet, opens the shutter, acquires the first-light frame, confirms
above-threshold mean signal, then closes the shutter for safe state.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

First-light is THE phase-defining commissioning event in any
synchrotron beamline literature (JWST / Rubin / IPAC). The scenario
unlocks four firsts in CORA's 2-BM doc tree:

  1. Phase `commissioning` is exercised for the first time (no prior
     scenario hangs there).
  2. New Family `Shutter` joins the cross-facility catalog.
  3. New Device `StationShutter` joins the 2-BM Asset inventory.
  4. New Procedure kind `first_light` joins the 2-BM Procedure list.

Per [[project_pilot_docs_design]] no doc page may name an aggregate
until a scenario test registers it.

## Distinction from `motor_homing` (shakedown phase)

Both are pre-science routines without proposal-driven users, but:

  - `motor_homing` (shakedown) exercises motorized Devices without
    beam. The beamline could be in any beam state; the routine only
    asserts motor behavior.
  - `first_light` (commissioning) asserts that BEAM reaches the
    detector. The routine cannot run before the front-end shutters
    are open and the optics chain is aligned (resolution / focus /
    center / roll / pitch from the `beta` phase). It is the
    transition signal from shakedown to first useful image.

## Domain shape (synthesized from APS commissioning practice)

Three-frame ceremony at low exposure to avoid scintillator damage:

  1. Verify safety shutter is closed. Acquire dark frame. Confirm
     mean pixel count is below a darkness threshold (electronics
     work, no light leak, no scintillator afterglow from prior
     beam).
  2. Open the safety shutter. Acquire first-light frame. Confirm
     mean pixel count is above a signal threshold (beam reached the
     scintillator, scintillator converted to visible, camera
     acquired).
  3. Close the safety shutter to return the chain to safe state.

Real commissioning runs typically follow with beam-position
alignment, flux normalization, and detector dark/flat baselines, but
each of those is its own scenario in this taxonomy.

## Asset stack (shutter + image chain)

  - StationShutter (the safety shutter; opens to admit beam, closes
    for safe state)
  - FLIR Oryx 5MP camera
  - LuAG scintillator

The rotation stage and sample stages are NOT in the target set:
first-light does not move them.

## What this scenario surfaces (gap-finding intent)

  - **Safety state is implicit.** The scenario brackets the
    open/close shutter operations around the acquire frames, but
    there is no machine-readable assertion that the shutter is open
    only during the bracketed acquire. Whether the Operation BC
    should carry a `safety_invariant` step_kind is a watch item.
  - **Dark/light threshold values are operator tribal knowledge.**
    "Mean count below 100" for dark and "mean count above 5000" for
    light are captured as Check evidence but not enforced anywhere;
    different detectors / scintillators give different absolute
    counts. Whether the Method should carry detector-specific
    threshold parameters is a watch item.
  - **First-light is non-repeatable.** A given Asset stack only
    truly has its FIRST first-light once; subsequent runs are
    re-verifications. The scenario name does not distinguish the
    two cases. Whether the first vs subsequent runs deserve
    different Procedure kinds (`first_light` vs `light_check`) is a
    watch item.
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

_NOW = datetime(2026, 5, 17, 13, 15, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000359bb")

# Facility hierarchy + operator Actor (Actor.id == _PRINCIPAL_ID)
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000359a01")

# Opaque Practice-site UUID (the practice site, unrelated to Asset tier).
_PRACTICE_SITE_ID = UUID("01900000-0000-7000-8000-000000359501")

# Family ids are derived from the name (deterministic uuid5), so they
# converge with what install_aps_unit defines and with cross-facility
# catalogs.
_CAP_SHUTTER_ID = family_stream_id(FamilyName("Shutter"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Devices (shutter + image chain)
_ASSET_SHUTTER_2BM_ID = UUID("01900000-0000-7000-8000-000000359a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000359a21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000359a31")

# Recipe ladder
_METHOD_FIRST_LIGHT_ID = UUID("01900000-0000-7000-8000-000000359d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e200")
_PRACTICE_FIRST_LIGHT_ID = UUID("01900000-0000-7000-8000-000000359d11")
_PLAN_FIRST_LIGHT_ID = UUID("01900000-0000-7000-8000-000000359d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000359f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000359f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000359f12")


_DEVICES = (
    DeviceSpec("StationShutter", _ASSET_SHUTTER_2BM_ID, "Shutter", _CAP_SHUTTER_ID),
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
        _METHOD_FIRST_LIGHT_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_FIRST_LIGHT_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_FIRST_LIGHT_ID,
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


def _shutter(
    *,
    state: str,
    role: str,
    sampled_at: datetime,
    note: str | None = None,
) -> ActivityInput:
    """Build a StationShutter Setpoint step input. `state` is `closed` or `open`."""
    payload: dict[str, Any] = {
        "channel": "StationShutter",
        "target_value": state,
        "units": "state",
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


def _signal_check(
    *,
    mean_count: float,
    threshold: float,
    direction: str,
    sampled_at: datetime,
    passed: bool = False,
    note: str | None = None,
) -> ActivityInput:
    """Check the camera frame mean count against a threshold.

    `direction="above"` means we expect mean > threshold (light frame);
    `direction="below"` means we expect mean < threshold (dark frame).
    """
    payload: dict[str, Any] = {
        "channel": "frame_mean_count",
        "passed": passed,
        "source": "image_analysis",
        "actual": mean_count,
        "evidence": {"threshold": threshold, "direction": direction},
    }
    if note is not None:
        payload["note"] = note
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
    from cora.operation.aggregates.procedure import PostgresActivityStore

    return PostgresActivityStore(db_pool)


@pytest.mark.integration
async def test_first_light_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + shutter + image chain, run the three-frame
    first-light ceremony (verify dark, open + acquire light, close to
    safe state), assert the auditable record carries dark-confirmed,
    light-passed, and safe-state-restored entries."""
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

    for asset_id in (_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: Method + Practice + Plan for the first-light routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )

    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="first_light",
            needed_family_ids=frozenset({_CAP_SHUTTER_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_first_light_practice",
            method_id=_METHOD_FIRST_LIGHT_ID,
            site_id=_PRACTICE_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_first_light_plan",
            practice_id=_PRACTICE_FIRST_LIGHT_ID,
            asset_ids=frozenset(
                {_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM first-light verification (Apr-2026 commissioning campaign)",
            kind="first_light",
            target_asset_ids=frozenset(
                {_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID}
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

    # ----- Procedure step entries: dark, light, safe-state -----
    #
    # Low exposure (50 ms) to avoid scintillator damage on first beam;
    # operator can extend later if signal is too low.

    t = _NOW
    dark_phase = (
        _shutter(
            state="closed",
            role="verify_safe_state",
            sampled_at=t,
            note="shutter must be closed before dark",
        ),
        _acquire(exposure_ms=50, sampled_at=t),
        _signal_check(
            mean_count=42.0,
            threshold=100.0,
            direction="below",
            sampled_at=t,
            passed=True,
            note="dark frame mean = 42 cnt, below 100 cnt threshold; electronics quiet",
        ),
    )
    light_phase = (
        _shutter(state="open", role="open_for_first_light", sampled_at=t, note="admit beam"),
        _acquire(exposure_ms=50, sampled_at=t),
        _signal_check(
            mean_count=8430.0,
            threshold=5000.0,
            direction="above",
            sampled_at=t,
            passed=True,
            note=(
                "first-light frame mean = 8430 cnt, above 5000 cnt threshold; "
                "beam reached scintillator"
            ),
        ),
    )
    safe_state = (
        _shutter(
            state="closed",
            role="return_to_safe_state",
            sampled_at=t,
            note="close to safe state after verification",
        ),
    )

    all_entries = dark_phase + light_phase + safe_state
    assert len(all_entries) == 7, "expected 7 entries for the first-light ceremony"

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=all_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 7

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

    for asset_id in (_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        asset_events, _ = await deps.event_store.load("Asset", asset_id)
        event_types = [e.event_type for e in asset_events]
        assert event_types == ["AssetRegistered", "AssetFamilyAdded", "AssetActivated"]

    # ----- Assert: 7 step entries land in the projection in canonical order -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 7
    assert [r["step_kind"] for r in rows] == [
        "setpoint",
        "action",
        "check",  # dark phase (shutter closed, verify quiet)
        "setpoint",
        "action",
        "check",  # light phase (shutter open, first light!)
        "setpoint",  # safe state (shutter closed)
    ]
