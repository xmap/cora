"""Continuous-rotation sweep at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Run
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for the N-back-to-back-Runs-share-Plan pattern: one
TomoScan call yields N child Runs (rotations) under a single
`Campaign(intent=Series)` with a shared Plan. Sourced from
`pre_apsu/ops/item_025.rst` (continuous-rotation pattern: 100
datasets x 1500 projections in one fly).

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

**First scenario-tier exercise of `Campaign.intent=Series`.** The
Campaign BC was designed with four intent-shape values (Series,
Sweep, Coordination, Block); to date only `Coordination` has been
exercised (proposal Campaign in O-1..O-6). This scenario fills in
`Series`: a chain of repetitions that share parameters and
plumbing, with only the Run-instance identity changing.

Real 2-BM continuous-rotation runs collect ~100 child Runs per
fly. The scenario uses N=3 (smallest count that's still a "series"
not a "single Run") to keep the test tight while demonstrating the
pattern. Naturally generalizes to larger N.

First scenario-tier exercise of:

  - `Campaign(intent=Series)` shape
  - Multiple Runs sharing ONE Plan (each Run is a separate aggregate
    but they bind to the same plan_id)
  - Multiple Datasets sharing ONE Subject + ONE Campaign (the per-
    Run Dataset chain)
  - `add_run_to_campaign` invoked N times against a Planned->Active
    Campaign (the FSM accepts adds across both states)

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. Continuous rotation
is a distinct operator routine from single-Run tomography (O-3):
different acquisition mode (fly-scan vs step-scan), different
event-shape (N RunStarted+RunCompleted pairs vs one), different
output (N Datasets vs one).

## Asset stack (full imaging chain, same as O-3)

Same Devices as `tomography_scan`. The continuous-rotation mode is
a Method-level distinction (different scan logic in TomoScan), not
a hardware-level distinction.

## What this scenario surfaces (gap-finding intent)

  - **Campaign.run_ids grows with each add.** After N adds, the
    Campaign aggregate has accumulated N child Run references in
    its bidirectional composition. Whether per-Run snapshots
    (rather than re-load-fold) become needed at large N is a
    watch item (per [[project_fold_cost_principles]] snapshots
    pattern).
  - **Subject is mounted once, measured once at the end.** A
    `Series` doesn't dismount/remount between Runs; the Subject
    stays Mounted across all N Runs and transitions to Measured
    only after the last completes. The mount lifecycle is a
    function of Subject identity not Run count.
  - **N Datasets share producing_run_id structure but differ
    per-Run.** Each Dataset's `producing_run_id` points at its
    own child Run; all share the same `subject_id`. Downstream
    lineage queries can group Datasets by Subject (giving the
    Series) or by Run (giving the single rotation).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign import bind as bind_add_run_to_campaign
from cora.campaign.features.close_campaign import CloseCampaign
from cora.campaign.features.close_campaign import bind as bind_close_campaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.campaign.features.start_campaign import bind as bind_start_campaign
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register_dataset
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.measure_subject import bind as bind_measure_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import operator_for
from tests.integration.scenarios._tomography_fixture import (
    RecipeSpec,
    TomographyAssetIds,
    define_recipe_ladder,
    install_and_activate_tomography_assets,
    recipe_ladder_id_prefix,
    tomography_install_id_prefix,
)

_NOW = datetime(2026, 5, 17, 17, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000412bb")

# Scenario tag: 412 (operations / continuous_rotation_sweep).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000412501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000412a01")

_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000412c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000412c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000412c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000412c31")

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000412a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000412a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000412a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000412a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000412b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000412b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000412b21")

_METHOD_FLYSCAN_ID = UUID("01900000-0000-7000-8000-000000412d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d2bb")
_PRACTICE_FLYSCAN_ID = UUID("01900000-0000-7000-8000-000000412d11")
_PLAN_FLYSCAN_ID = UUID("01900000-0000-7000-8000-000000412d21")

# N = 3 child Runs in the Series (smallest count that demonstrates the pattern).
_RUN_IDS = (
    UUID("01900000-0000-7000-8000-000000412f01"),
    UUID("01900000-0000-7000-8000-000000412f02"),
    UUID("01900000-0000-7000-8000-000000412f03"),
)
_DATASET_IDS = (
    UUID("01900000-0000-7000-8000-000000412f11"),
    UUID("01900000-0000-7000-8000-000000412f12"),
    UUID("01900000-0000-7000-8000-000000412f13"),
)

_TOMO_ASSETS = TomographyAssetIds(
    unit_id=_2BM_UNIT_ID,
    rotary_cap_id=_CAP_ROTARY_STAGE_ID,
    linear_x_cap_id=_CAP_LINEAR_STAGE_ID,
    camera_cap_id=_CAP_CAMERA_ID,
    scintillator_cap_id=_CAP_SCINTILLATOR_ID,
    rotary_id=_ASSET_AEROTECH_ABRS_ID,
    linear_x_id=_ASSET_SAMPLE_TOP_X_ID,
    camera_id=_ASSET_ORYX_5MP_ID,
    scintillator_id=_ASSET_SCINTILLATOR_LUAG_ID,
)

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1234 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 continuous-rotation series",
    campaign_intent=CampaignIntent.SERIES,
    campaign_tags=frozenset({"proposal", "continuous_rotation", "tomography", "porous_media"}),
)


_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_FLYSCAN_ID,
    method_name="continuous_rotation_tomography",
    needed_family_ids=frozenset(
        {_CAP_ROTARY_STAGE_ID, _CAP_LINEAR_STAGE_ID, _CAP_CAMERA_ID, _CAP_SCINTILLATOR_ID}
    ),
    parameters_schema={
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "exposure_ms": {"type": "integer", "minimum": 1},
            "n_projections": {"type": "integer", "minimum": 1},
            "angle_range_deg": {"type": "number", "minimum": 1, "maximum": 360},
            "rotation_index": {"type": "integer", "minimum": 0},
        },
        "required": ["exposure_ms", "n_projections", "angle_range_deg"],
    },
    practice_id=_PRACTICE_FLYSCAN_ID,
    practice_name="2BM_continuous_rotation_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_FLYSCAN_ID,
    plan_name="2BM_continuous_rotation_plan",
    plan_asset_ids=frozenset(
        {
            _ASSET_AEROTECH_ABRS_ID,
            _ASSET_SAMPLE_TOP_X_ID,
            _ASSET_ORYX_5MP_ID,
            _ASSET_SCINTILLATOR_LUAG_ID,
        }
    ),
)


def _id_queue() -> list[UUID]:
    e = uuid4
    ids: list[UUID] = [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        e(),  # start_campaign (Planned -> Active; before the loop)
    ]
    # Per child Run: start_run (run_id + event) + add_run_to_campaign (2 event ids) +
    # complete_run (event) + register_dataset (dataset_id + event) = 7 ids.
    for run_id, dataset_id in zip(_RUN_IDS, _DATASET_IDS, strict=True):
        ids.extend(
            [
                run_id,
                e(),  # start_run
                e(),
                e(),  # add_run_to_campaign
                e(),  # complete_run
                dataset_id,
                e(),  # register_dataset
            ]
        )
    ids.append(e())  # measure_subject (once after all Runs complete)
    ids.append(e())  # close_campaign (Active -> Closed; after measure_subject)
    return ids


@pytest.mark.integration
async def test_continuous_rotation_sweep_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate, open Series-intent Campaign,
    mount Subject once, run N=3 child Runs sequentially each sharing
    the same Plan + Subject, each adding to the same Campaign, each
    producing its own Dataset. Subject Measured fires once at the end.
    Assert all N Runs landed cleanly and the Campaign accumulated N
    member-add events."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_and_activate_tomography_assets(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        asset_ids=_TOMO_ASSETS,
    )

    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=_SUBJECT_ID,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="continuous-rotation series setup; sample stays mounted across all N child Runs",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await define_recipe_ladder(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_RECIPE,
    )

    # ----- Campaign BC: Planned -> Active before the Run loop -----
    # Series Campaign goes live for the sweep. add_run_to_campaign accepts
    # Planned too, but explicit start_campaign matches operator narrative
    # (operator declares "series is live" before kicking off rotation 1).

    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- N=3 child Runs, each sharing the same Plan + Subject + Campaign -----

    for idx, (run_id, _dataset_id) in enumerate(zip(_RUN_IDS, _DATASET_IDS, strict=True)):
        await bind_start_run(deps)(
            StartRun(
                name=f"continuous-rotation child Run {idx + 1}/3",
                plan_id=_PLAN_FLYSCAN_ID,
                subject_id=_SUBJECT_ID,
                override_parameters={
                    "exposure_ms": 100,
                    "n_projections": 1500,
                    "angle_range_deg": 180.0,
                    "rotation_index": idx,
                },
                trigger_source=f"continuous-rotation series; rotation {idx + 1} of 3",
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_add_run_to_campaign(deps)(
            AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_complete_run(deps)(
            CompleteRun(run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_register_dataset(deps)(
            RegisterDataset(
                name=f"Proposal_2026-1234_sample_A_rotation_{idx + 1:02d}",
                uri=(
                    f"file:///data/2026-05/Dr_PI/"
                    f"Proposal_2026-1234_sample_A_rotation_{idx + 1:02d}.h5"
                ),
                checksum_algorithm="sha256",
                checksum_value=f"{(idx + 1) % 16:x}" * 64,
                byte_size=12_582_912_000,
                media_type="application/x-hdf5",
                conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
                producing_run_id=run_id,
                subject_id=_SUBJECT_ID,
                derived_from=frozenset(),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Subject Measured fires once at the end (after the last Run completes;
    # mount-and-measure is per-Subject, not per-Run).
    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: close the sweep (Active -> Closed) -----
    # Series complete; close locks membership.

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: each child Run reached terminal Completed -----

    for run_id in _RUN_IDS:
        run_events, _run_version = await deps.event_store.load("Run", run_id)
        run_event_types = [e.event_type for e in run_events]
        assert "RunStarted" in run_event_types
        assert "RunAddedToCampaign" in run_event_types
        assert "RunCompleted" in run_event_types

    # ----- Assert: Campaign accumulated N CampaignRunAdded events -----

    campaign_events, _campaign_version = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert campaign_event_types.count("CampaignRegistered") == 1
    assert campaign_event_types.count("CampaignRunAdded") == 3
    assert campaign_event_types.count("CampaignStarted") == 1
    assert campaign_event_types.count("CampaignClosed") == 1

    # ----- Assert: each Dataset references its own producing_run_id -----

    for run_id, dataset_id in zip(_RUN_IDS, _DATASET_IDS, strict=True):
        dataset_events, dataset_version = await deps.event_store.load("Dataset", dataset_id)
        assert dataset_version == 1
        dataset_payload = dataset_events[0].payload
        assert UUID(dataset_payload["producing_run_id"]) == run_id
        assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID

    # ----- Assert: Subject lifecycle Mounted-once + Measured-once -----

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
    ]
