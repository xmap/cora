"""Mosaic-tile tomography acquisition at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Run
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for a 2x2 spatial-mosaic acquisition: a Subject too
wide for the camera FOV is imaged as four tile Runs at different
sample-stage positions, all under a single `Coordination` Campaign
so the downstream stitch step has a stable parent grouping.

Sourced from 2-BM operator practice: when the Subject footprint
exceeds a single FOV, the operator pre-plans a tile grid (in
2-BM jargon, a "mosaic") and runs each tile as its own Run sharing
Plan + Subject + Campaign with the others. Tiles are stitched
into a single reconstruction downstream.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_campaign_design]] for the four
`CampaignIntent` values and their distinctions.

## Why this scenario exists

The `Campaign(Coordination)` intent is the third of four intent
shapes ([[project_campaign_design]]); `Series` is exercised by
`test_2bm_continuous_rotation_sweep.py`. `Coordination` differs
from `Series` in that the child Runs are not independent
replicates: each one carries a tile-grid coordinate, and the
downstream value comes from stitching all N together. Losing
one tile reduces the reconstruction's coverage, not just the
statistical power.

This scenario exercises:

  - Per-Run spatial-coordinate overrides on a shared Plan
    (`tile_x_mm` / `tile_y_mm` / `tile_index`)
  - A Campaign whose `intent=Coordination` and whose member Run
    count is fixed by the tile grid (N=4 for a 2x2)
  - One Dataset per tile-Run, each referencing the same Subject
    but a distinct producing Run

## Domain shape (operator narrative)

  1. Operator opens beamtime; mounts a wide Subject too large
     for a single FOV.
  2. Operator pre-plans a 2x2 tile grid (positions chosen so
     adjacent tiles overlap ~10% for the stitch).
  3. Coordination Campaign opens; the four tile Runs will all
     attach to it.
  4. For each tile (i, j) in {(0,0), (0,1), (1,0), (1,1)}:
       - Start a Run with override_parameters carrying tile_x_mm,
         tile_y_mm, tile_index.
       - Add the Run to the Coordination Campaign.
       - Complete the Run.
       - Register the tile's raw projection Dataset.
  5. After all four tiles complete, Subject reaches Measured
     once (mount-and-measure is per-Subject, not per-Run).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The mosaic shape
and the continuous-rotation series share the multi-Run-per-Subject
structure but differ on `CampaignIntent`, on the parameter-sweep
shape (spatial-grid vs replicate), and on the downstream
processing assumption (stitch vs average). Bundling them would
hide the design intent of distinguishing `Coordination` from
`Series`.

## What this scenario surfaces (gap-finding intent)

  - **Coordination intent has no aggregate-side enforcement of
    tile-completeness.** `Campaign(Coordination)` does not (today)
    refuse to `close` if one of its expected tiles is missing.
    Whether a future `expected_run_count` constraint should land
    on Campaign is a watch item; for now the contract is
    operator-discipline + Dataset-side validation downstream.
  - **No "tile manifest" projection yet.** A downstream stitch
    consumer would benefit from a projection over the Coordination
    Campaign that lists each member Run's `tile_index` for fast
    lookup. Not built; `tile_index` lives in each Run's
    `effective_parameters` snapshot.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

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
from cora.equipment.aggregates.family import FamilyName, family_stream_id
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

_NOW = datetime(2026, 5, 17, 20, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000422bb")

# Scenario tag: 422 (operations / mosaic_acquisition).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000422501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000422a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000422a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000422a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000422a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000422a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000422b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000422b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000422b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000422d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d162")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000422d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000422d21")

# N = 4 tile Runs (2x2 mosaic).
_RUN_IDS = (
    UUID("01900000-0000-7000-8000-000000422f01"),
    UUID("01900000-0000-7000-8000-000000422f02"),
    UUID("01900000-0000-7000-8000-000000422f03"),
    UUID("01900000-0000-7000-8000-000000422f04"),
)
_DATASET_IDS = (
    UUID("01900000-0000-7000-8000-000000422f11"),
    UUID("01900000-0000-7000-8000-000000422f12"),
    UUID("01900000-0000-7000-8000-000000422f13"),
    UUID("01900000-0000-7000-8000-000000422f14"),
)

# 2x2 tile grid: (tile_index, tile_x_mm, tile_y_mm). Spacing chosen so adjacent
# tiles overlap ~10% for the downstream stitch (illustrative numbers only).
_TILES: tuple[tuple[int, float, float], ...] = (
    (0, 0.0, 0.0),
    (1, 1.8, 0.0),
    (2, 0.0, 1.8),
    (3, 1.8, 1.8),
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
    pi_actor_name="Proposal 2026-1236 PI",
    subject_id=_SUBJECT_ID,
    subject_name="wide sandstone slab (Proposal 2026-1236, mosaic acquisition)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1236 2x2 tile mosaic",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "mosaic", "tomography", "porous_media"}),
)


_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_TOMO_ID,
    method_name="mosaic_tomography",
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
            "tile_index": {"type": "integer", "minimum": 0},
            "tile_x_mm": {"type": "number"},
            "tile_y_mm": {"type": "number"},
        },
        "required": [
            "exposure_ms",
            "n_projections",
            "angle_range_deg",
            "tile_index",
            "tile_x_mm",
            "tile_y_mm",
        ],
    },
    practice_id=_PRACTICE_TOMO_ID,
    practice_name="2BM_mosaic_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_TOMO_ID,
    plan_name="2BM_mosaic_plan",
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
        e(),  # start_campaign (Planned -> Active; before tile loop)
    ]
    # Per tile Run: start_run (run_id + event) + add_run_to_campaign (2) +
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
    ids.append(e())  # measure_subject (once after all tiles)
    ids.append(e())  # close_campaign (Active -> Closed; mosaic complete)
    return ids


@pytest.mark.integration
async def test_mosaic_acquisition_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate, open Coordination Campaign,
    mount wide Subject once, run N=4 tile Runs at distinct (x, y)
    grid positions each producing its own Dataset, then measure
    the Subject. Assert all tiles landed cleanly and the Campaign
    carries N member-add events."""
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
            reason="mosaic acquisition setup; sample stays mounted across all N tile Runs",
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

    # ----- Campaign BC: Planned -> Active before the tile loop -----

    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- N=4 tile Runs, each at a distinct (x, y) grid position -----

    for (tile_index, tile_x_mm, tile_y_mm), run_id, _dataset_id in zip(
        _TILES, _RUN_IDS, _DATASET_IDS, strict=True
    ):
        await bind_start_run(deps)(
            StartRun(
                name=f"mosaic tile {tile_index} (x={tile_x_mm}mm, y={tile_y_mm}mm)",
                plan_id=_PLAN_TOMO_ID,
                subject_id=_SUBJECT_ID,
                override_parameters={
                    "exposure_ms": 100,
                    "n_projections": 1500,
                    "angle_range_deg": 180.0,
                    "tile_index": tile_index,
                    "tile_x_mm": tile_x_mm,
                    "tile_y_mm": tile_y_mm,
                },
                trigger_source=f"mosaic acquisition; tile {tile_index + 1} of 4",
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
                name=f"Proposal_2026-1236_mosaic_tile_{tile_index:02d}",
                uri=(
                    f"file:///data/2026-05/Dr_PI/Proposal_2026-1236_mosaic_tile_{tile_index:02d}.h5"
                ),
                checksum_algorithm="sha256",
                checksum_value=f"{(tile_index + 1) % 16:x}" * 64,
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

    # Subject Measured fires once at the end (after the last tile completes).
    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: close the mosaic (Active -> Closed) -----

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: each tile Run reached terminal Completed -----

    for run_id in _RUN_IDS:
        run_events, _ = await deps.event_store.load("Run", run_id)
        run_event_types = [e.event_type for e in run_events]
        assert "RunStarted" in run_event_types
        assert "RunAddedToCampaign" in run_event_types
        assert "RunCompleted" in run_event_types

    # ----- Assert: Coordination Campaign accumulated N CampaignRunAdded events -----

    campaign_events, _ = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert campaign_event_types.count("CampaignRegistered") == 1
    assert campaign_event_types.count("CampaignRunAdded") == 4
    assert campaign_event_types.count("CampaignStarted") == 1
    assert campaign_event_types.count("CampaignClosed") == 1

    # ----- Assert: each tile Dataset references its own producing_run_id -----

    for run_id, dataset_id in zip(_RUN_IDS, _DATASET_IDS, strict=True):
        dataset_events, dataset_version = await deps.event_store.load("Dataset", dataset_id)
        assert dataset_version == 1
        dataset_payload = dataset_events[0].payload
        assert UUID(dataset_payload["producing_run_id"]) == run_id
        assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID
