"""Detector dark baseline at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Data, Equipment, Operation, Recipe

Scenario test for the dark-baseline routine: with the shutter closed,
acquire a stack of N dark frames, compute a pixel-wise mean + std,
and register the resulting baseline as a Dataset for downstream
reconstruction to subtract. Runs after `first_light` but before any
science Run; produces the baseline that every subsequent Run consumes
to remove detector dark current.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Three firsts in CORA's 2-BM doc tree:

  1. First exercise of the Data BC (`register_dataset`) in any
     scenario. Unlocks `2-bm/datasets.md`.
  2. First scenario where a Procedure produces a downstream artifact
     captured as a Dataset, validating the "Procedure logs the
     operator actions; Dataset registers the artifact" pattern.
  3. First commissioning-phase Procedure that depends on a prior
     commissioning Procedure (`first_light`). The dependency is a
     documentation claim on `procedures.md`, not an enforced
     invariant in code.

## Domain shape (universal across CT facilities)

Dark baselines are reconstruction-baseline data that any modern CT
pipeline (`tomopy`, ASTRA, plain numpy) subtracts from raw
projections before further processing:

  1. Verify safety shutter is closed.
  2. Acquire N dark frames at the same exposure that science
     projections will use.
  3. Compute pixel-wise mean and standard deviation across the
     stack. Hot-pixel candidates surface as outliers in the std map.
  4. Store the baseline (typically as HDF5 / NeXus) so future Runs
     can subtract it.

Typical: 50 frames at 200 ms each (10s of integration). The mean
captures dark current; the std characterises read noise. Hot pixels
above ~5x the median std flag pixels to mask in reconstruction.

## Asset stack (shutter + image chain)

Same as `first_light`: StationShutter, Camera, Scintillator.
Dark baseline does not move any motors.

## What this scenario surfaces (gap-finding intent)

  - **N-frame burst is one Action, not N actions.** The acquire-
    dark-stack step is a single `Action` carrying `n_frames` in
    params; expanding to N individual Actions would clutter the
    Procedure log without adding domain information. Whether the
    polymorphic Action payload should grow a canonical `burst`
    discriminator is a watch item.
  - **Baseline computation is operator-offline.** Mean + std are
    computed outside CORA (in `tomopy` or equivalent) and the
    operator records the outcome on a Check entry as evidence. The
    raw frames live in the registered Dataset; the summary
    statistics live on the Check. Whether the Dataset should carry
    derived statistics as structured metadata is a watch item.
  - **Trial vs Production lineage.** The Dataset lands as Trial by
    default per the Data BC design; `promote_dataset` is a
    separate slice that gates Production. This scenario leaves the
    baseline as Trial; production lineage is an `operations`-phase
    concern.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
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

_NOW = datetime(2026, 5, 17, 13, 45, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000003a5bb")

# Facility hierarchy
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_APS_SITE_ID = UUID("01900000-0000-7000-8000-00000035a501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-00000035aa01")

# Capabilities
_CAP_SHUTTER_ID = family_stream_id(FamilyName("Shutter"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

# Devices
_ASSET_SHUTTER_2BM_ID = UUID("01900000-0000-7000-8000-00000035aa11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-00000035aa21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-00000035aa31")

# Recipe ladder
_METHOD_DARK_ID = UUID("01900000-0000-7000-8000-00000035ad01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ee59")
_PRACTICE_DARK_ID = UUID("01900000-0000-7000-8000-00000035ad11")
_PLAN_DARK_ID = UUID("01900000-0000-7000-8000-00000035ad21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-00000035af01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-00000035af11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-00000035af12")

# Dataset (the artifact this Procedure produces)
_DATASET_DARK_BASELINE_ID = UUID("01900000-0000-7000-8000-00000035af21")


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
        # activate_asset x 3
        e(),
        e(),
        e(),
        # define_method
        _METHOD_DARK_ID,
        e(),
        # define_practice
        _PRACTICE_DARK_ID,
        e(),
        # define_plan
        _PLAN_DARK_ID,
        e(),
        # register_procedure
        _PROCEDURE_ID,
        e(),
        # start_procedure
        e(),
        # append_activities (lazy open): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure
        e(),
        # register_dataset
        _DATASET_DARK_BASELINE_ID,
        e(),
    ]


def _shutter(
    *, state: str, role: str, sampled_at: datetime, note: str | None = None
) -> ActivityInput:
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


def _acquire_dark_stack(*, n_frames: int, exposure_ms: int, sampled_at: datetime) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_dark_stack",
            "params": {"n_frames": n_frames, "exposure_ms": exposure_ms},
        },
        sampled_at=sampled_at,
    )


def _compute_baseline(*, algorithm: str, sampled_at: datetime) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "compute_baseline",
            "params": {"algorithm": algorithm},
        },
        sampled_at=sampled_at,
    )


def _check_stack(
    *,
    channel: str,
    passed: bool,
    sampled_at: datetime,
    evidence: dict[str, Any],
) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="check",
        payload={
            "channel": channel,
            "passed": passed,
            "source": "tomopy.misc.morph",
            "evidence": evidence,
        },
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
async def test_dark_baseline_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + image chain, acquire 50 dark frames with shutter
    closed, compute pixel-wise baseline, register the resulting Dataset
    for downstream Runs to subtract."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Install the 2-BM facility hierarchy + the 3 Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: activate all 3 Devices -----

    for asset_id in (_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: Method + Practice + Plan for the dark-baseline routine -----

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
            name="dark_baseline",
            needed_family_ids=frozenset({_CAP_SHUTTER_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_dark_baseline_practice",
            method_id=_METHOD_DARK_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_dark_baseline_plan",
            practice_id=_PRACTICE_DARK_ID,
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
            name="2-BM dark baseline (50 frames @ 200ms, Apr-2026 campaign)",
            kind="dark_baseline",
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

    # ----- Procedure step entries: verify dark, acquire stack, compute baseline -----

    t = _NOW
    all_entries = (
        _shutter(
            state="closed",
            role="verify_safe_state",
            sampled_at=t,
            note="shutter must be closed for dark",
        ),
        _acquire_dark_stack(n_frames=50, exposure_ms=200, sampled_at=t),
        _check_stack(
            channel="dark_stack_acquired",
            passed=True,
            sampled_at=t,
            evidence={
                "frames_captured": 50,
                "dark_pixel_mean": 42.1,
                "dark_pixel_std": 2.7,
                "hot_pixel_count": 3,
            },
        ),
        _compute_baseline(algorithm="mean_pixel_wise", sampled_at=t),
        _check_stack(
            channel="baseline_quality",
            passed=True,
            sampled_at=t,
            evidence={
                "baseline_pixel_mean": 42.1,
                "baseline_pixel_std": 2.7,
                "ready_for_subtraction": True,
            },
        ),
    )
    assert len(all_entries) == 5

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=all_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 5

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Data BC: register the dark-baseline Dataset (out-of-Procedure artifact) -----
    #
    # `subject_id=None` per the design doc: calibration / dark-field / synthetic
    # data with no sample has no Subject. `producing_run_id=None`: no Run was
    # opened (commissioning Procedures stand alone outside a science Run).

    await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_dark_baseline_2026-04-17",
            uri="file:///data/2bm/2026-04/dark_baseline.h5",
            checksum_algorithm="sha256",
            checksum_value="d" * 64,
            byte_size=2448 * 2048 * 2 * 50,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXdark_field"}),
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
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

    # ----- Assert: 5 step entries land in the projection -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 5
    assert [r["step_kind"] for r in rows] == [
        "setpoint",  # verify shutter closed
        "action",  # acquire dark stack
        "check",  # stack acquired
        "action",  # compute baseline
        "check",  # baseline quality
    ]

    # ----- Assert: Dataset stream landed -----

    dataset_events, dataset_version = await deps.event_store.load(
        "Dataset", _DATASET_DARK_BASELINE_ID
    )
    assert dataset_version == 1
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    dataset_payload = dataset_events[0].payload
    assert dataset_payload["name"] == "2BM_dark_baseline_2026-04-17"
    assert dataset_payload["encoding"]["media_type"] == "application/x-hdf5"
    assert dataset_payload["subject_id"] is None
    assert dataset_payload["producing_run_id"] is None
