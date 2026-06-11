"""Detector flat-field baseline at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Data, Equipment, Operation, Recipe

Scenario test for the flat-field baseline routine: with the shutter
open and NO sample in the beam, acquire a stack of N flat frames,
compute a pixel-wise mean, and register the resulting baseline as a
Dataset for downstream reconstruction to divide by. Sibling to
`dark_baseline`; same structural shape with the shutter
state and analytic operation inverted.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

To complete the dark + flat pair that every CT reconstruction
requires:

  reconstructed_projection = (raw - dark) / (flat - dark)

Dark removes additive detector offset; flat removes multiplicative
beam-profile non-uniformity. Without both baselines registered as
Datasets, the operations-phase science Runs have nothing to
normalize against.

## Distinction from `dark_baseline`

  - Dark: shutter CLOSED, no beam reaches detector. Captures dark
    current + read noise.
  - Flat: shutter OPEN, no sample in beam path. Captures the
    incoming beam's spatial profile + scintillator response + camera
    gain map.

Both produce a Dataset; both are calibration (subject_id=None,
producing_run_id=None); both are Trial intent initially and require
`promote_dataset` (deferred) to reach Production.

## Domain shape (universal across CT facilities)

  1. Verify the safety shutter is closed (safe starting state).
  2. Confirm sample is OUT of the beam path. The scenario captures
     this as an operator-asserted Check; in production CORA could
     query a Subject's mount status, but this scenario does not
     model that.
  3. Open the shutter. Acquire N flat frames at the same exposure
     that science projections will use.
  4. Compute pixel-wise mean across the stack. The mean image is
     the flat baseline.
  5. Close the shutter to safe state.
  6. Register the baseline as a Dataset.

Typical: 50 frames at 200 ms each. Mean count should match the
first-light light frame (above ~5000 cnt for the standard setup),
confirming consistent beam delivery.

## Asset stack (shutter + image chain)

Same as `first_light` and `dark_baseline`:
Shutter_2BM, Oryx_5MP_camera, Scintillator_LuAG.

## What this scenario surfaces (gap-finding intent)

  - **"Sample out of beam" is an operator assertion, not a CORA
    invariant.** The scenario records the assertion as a Check
    entry but cannot verify it. Whether the Subject BC should
    model "in-beam" / "out-of-beam" mount status (and gate
    flat-field acquisition on it) is a watch item.
  - **Dark and flat lineage on Datasets.** This baseline does not
    declare `derived_from` even though, in some pipelines, the
    flat is dark-subtracted before storage. The scenario keeps the
    raw flat separate; a later scenario could register a
    dark-subtracted-flat with `derived_from` pointing at both this
    flat and the dark baseline.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
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

_NOW = datetime(2026, 5, 17, 14, 15, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000003b5bb")

# Facility hierarchy
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID
_APS_SITE_ID = UUID("01900000-0000-7000-8000-00000035b501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-00000035ba01")

# Capabilities
_CAP_SHUTTER_ID = UUID("01900000-0000-7000-8000-00000035bc01")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-00000035bc11")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-00000035bc21")

# Devices
_ASSET_SHUTTER_2BM_ID = UUID("01900000-0000-7000-8000-00000035ba11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-00000035ba21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-00000035ba31")

# Recipe ladder
_METHOD_FLAT_ID = UUID("01900000-0000-7000-8000-00000035bd01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e61f")
_PRACTICE_FLAT_ID = UUID("01900000-0000-7000-8000-00000035bd11")
_PLAN_FLAT_ID = UUID("01900000-0000-7000-8000-00000035bd21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-00000035bf01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-00000035bf11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-00000035bf12")

# Dataset (the artifact this Procedure produces)
_DATASET_FLAT_BASELINE_ID = UUID("01900000-0000-7000-8000-00000035bf21")


_DEVICES = (
    DeviceSpec("Shutter_2BM", _ASSET_SHUTTER_2BM_ID, "Shutter", _CAP_SHUTTER_ID),
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
        # activate_asset x 3
        e(),
        e(),
        e(),
        # define_method
        _METHOD_FLAT_ID,
        e(),
        # define_practice
        _PRACTICE_FLAT_ID,
        e(),
        # define_plan
        _PLAN_FLAT_ID,
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
        _DATASET_FLAT_BASELINE_ID,
        e(),
    ]


def _shutter(
    *, state: str, role: str, sampled_at: datetime, note: str | None = None
) -> ActivityInput:
    payload: dict[str, Any] = {
        "channel": "Shutter_2BM",
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


def _acquire_flat_stack(*, n_frames: int, exposure_ms: int, sampled_at: datetime) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="action",
        payload={
            "action_name": "acquire_flat_stack",
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


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    evidence: dict[str, Any],
) -> ActivityInput:
    return ActivityInput(
        event_id=uuid4(),
        step_kind="check",
        payload={
            "channel": channel,
            "passed": passed,
            "source": source,
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
async def test_flat_baseline_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + image chain, confirm sample out, open shutter,
    acquire 50 flat frames, compute pixel-wise mean baseline, close
    shutter, register the resulting Dataset for downstream Runs to
    divide by."""
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

    # ----- Recipe BC: Method + Practice + Plan for the flat-baseline routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.acquisition",
        name="Acquisition",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="flat_baseline",
            needed_family_ids=frozenset({_CAP_SHUTTER_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_flat_baseline_practice",
            method_id=_METHOD_FLAT_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_flat_baseline_plan",
            practice_id=_PRACTICE_FLAT_ID,
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
            name="2-BM flat-field baseline (50 frames @ 200ms, Apr-2026 campaign)",
            kind="flat_baseline",
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

    # ----- Procedure step entries: verify sample-out, open + acquire + close, compute -----

    t = _NOW
    all_entries = (
        _check(
            channel="sample_in_beam",
            passed=True,
            source="operator_visual",
            sampled_at=t,
            evidence={"asserted": False, "note": "operator confirmed sample stage retracted"},
        ),
        _shutter(
            state="closed", role="verify_safe_state", sampled_at=t, note="starting safe state"
        ),
        _shutter(
            state="open",
            role="open_for_flat_field",
            sampled_at=t,
            note="admit beam, no sample in path",
        ),
        _acquire_flat_stack(n_frames=50, exposure_ms=200, sampled_at=t),
        _check(
            channel="flat_stack_acquired",
            passed=True,
            source="tomopy.misc.morph",
            sampled_at=t,
            evidence={
                "frames_captured": 50,
                "flat_pixel_mean": 8430.0,
                "flat_pixel_std": 142.0,
                "uniformity_cov": 0.017,
            },
        ),
        _shutter(
            state="closed",
            role="return_to_safe_state",
            sampled_at=t,
            note="close after acquisition",
        ),
        _compute_baseline(algorithm="mean_pixel_wise", sampled_at=t),
        _check(
            channel="baseline_quality",
            passed=True,
            source="tomopy.misc.morph",
            sampled_at=t,
            evidence={
                "baseline_pixel_mean": 8430.0,
                "ready_for_division": True,
            },
        ),
    )
    assert len(all_entries) == 8

    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureActivities(procedure_id=_PROCEDURE_ID, entries=all_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 8

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Data BC: register the flat-field-baseline Dataset -----

    await bind_register_dataset(deps)(
        RegisterDataset(
            name="2BM_flat_baseline_2026-04-17",
            uri="file:///data/2bm/2026-04/flat_baseline.h5",
            checksum_algorithm="sha256",
            checksum_value="f" * 64,
            byte_size=2448 * 2048 * 2 * 50,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXflat_field"}),
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Procedure stream lifecycle -----

    events, version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert version == 4
    assert [e.event_type for e in events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureActivitiesLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert: target Assets reached Active lifecycle -----

    for asset_id in (_ASSET_SHUTTER_2BM_ID, _ASSET_ORYX_5MP_ID, _ASSET_SCINTILLATOR_LUAG_ID):
        asset_events, _ = await deps.event_store.load("Asset", asset_id)
        assert [e.event_type for e in asset_events] == [
            "AssetRegistered",
            "AssetFamilyAdded",
            "AssetActivated",
        ]

    # ----- Assert: 8 step entries land in the projection in canonical order -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_activities "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 8
    assert [r["step_kind"] for r in rows] == [
        "check",  # sample-out assertion
        "setpoint",  # verify shutter closed (safe start)
        "setpoint",  # open shutter
        "action",  # acquire flat stack
        "check",  # stack acquired
        "setpoint",  # close shutter (safe state)
        "action",  # compute baseline
        "check",  # baseline quality
    ]

    # ----- Assert: Dataset stream landed -----

    dataset_events, dataset_version = await deps.event_store.load(
        "Dataset", _DATASET_FLAT_BASELINE_ID
    )
    assert dataset_version == 1
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    dataset_payload = dataset_events[0].payload
    assert dataset_payload["name"] == "2BM_flat_baseline_2026-04-17"
    assert dataset_payload["encoding"]["media_type"] == "application/x-hdf5"
    assert dataset_payload["subject_id"] is None
    assert dataset_payload["producing_run_id"] is None
