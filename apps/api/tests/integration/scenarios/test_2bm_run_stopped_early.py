"""Controlled-exit Run.stop at APS 2-BM.

cluster: Runs
archetype: routine
bc_primary: Run
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for the operator-driven controlled-exit pathway:
a tomography scan is in flight when the operator decides the
data acquired so far is sufficient (live-reconstruction quality
already exceeds target, sample-of-opportunity shows the
phenomenon of interest in the first 600 projections, calibration
sample's information content is saturated). The operator stops
the Run before the planned 1500-projection target. The Run
transitions Running -> Stopped; data is valid up to the stop
point; the Dataset is registered for downstream review.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. The stop_run slice is the controlled-exit terminal
distinct from abort (emergency-exit) and complete (planned
target reached).

## Why this scenario exists

**First scenario-tier exercise of `stop_run`.** Sibling scenarios
in this batch:

  - `test_2bm_run_hold_resume_cycle.py` covers hold/resume.
  - THIS scenario covers `stop_run` (Running -> Stopped).
  - `test_2bm_run_truncated_after_outage.py` covers `truncate_run`.

This scenario exercises:

  - `stop_run` from `Running` (the most common source state;
    the alternative is `Held -> Stopped`).
  - The `reason` field on `stop_run` (required, 1-500 chars).
    Distinct from `complete_run` which has no reason because
    "the planned target reached" is its own signal.
  - Stop semantics: data IS valid up to the stop point. The
    operator registers the resulting partial Dataset. This is
    different from abort (data flagged potentially invalid)
    and truncate (data definitely partial because the system
    was de-facto dead).

## Domain shape (operator narrative)

  1. Beamtime intake + sample mounted + recipe ladder defined.
  2. Operator starts a 1500-projection tomography scan as a
     "save the data and look" scan on a sample-of-opportunity
     (the PI dropped off an extra core from a previous-proposal
     leftover; no formal study, just looking).
  3. ~600 projections in, the operator inspects the live-reco
     and concludes the porosity features are clearly visible;
     no need to acquire the remaining 900 projections (saves
     ~30 minutes for the next user).
  4. Operator stops the Run via `stop_run` with a reason citing
     "live-reco saturated; data sufficient for the
     sample-of-opportunity look". The Run transitions
     Running -> Stopped.
  5. Operator registers the resulting partial Dataset; the
     scan-tier downstream consumers understand stop semantics
     and treat the partial data as valid.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. Three terminal-
exit shapes (Completed / Stopped / Aborted) each carry distinct
operator-narrative + downstream-consumer implications. Bundling
stop with complete (covered by O-3 tomography_scan) would lose
the operator-decision distinction; bundling with abort (covered
by `test_2bm_run_debrief_aborted.py`) would conflate controlled-
exit with emergency-exit.

## What this scenario surfaces (gap-finding intent)

  - **Dataset registered post-stop has no "partial" flag.** The
    Dataset aggregate carries no field marking "the producing
    Run was stopped, not completed"; downstream consumers must
    correlate via `producing_run_id -> Run.status` to know.
    Whether a `partial: bool` field on Dataset is needed is a
    watch item (per `project_dataset_lineage_design.md`).
  - **The RunDebriefer agent's 5-value choice taxonomy has no
    direct `EarlyStop` value.** A Stopped Run would likely
    surface as `NominalCompletion` or `DegradedCompletion`
    depending on context; whether the agent should classify
    `StoppedEarly` separately (or fold it into DegradedCompletion
    with operator-decision flavor) is a watch item for the
    sibling `test_2bm_run_debrief_*` family.
  - **No projection over stop_run reasons.** A future "why do
    operators stop scans?" analysis would benefit from a
    projection over `RunStopped.reason`; not built today.
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
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.run.features.stop_run import StopRun
from cora.run.features.stop_run import bind as bind_stop_run
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

_NOW = datetime(2026, 5, 18, 4, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000461bb")

# Scenario tag: 461 (run mid-lifecycle / stopped early).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000461501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000461a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000461a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000461a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000461a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000461a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000461b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000461b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000461b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000461d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dc99")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000461d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000461d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000461f02")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000461f11")

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
    pi_actor_name="Sample-of-opportunity PI",
    subject_id=_SUBJECT_ID,
    subject_name="leftover sandstone core (sample-of-opportunity)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Sample-of-opportunity scan (early-stop)",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"sample_of_opportunity", "tomography", "porous_media"}),
)


_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_TOMO_ID,
    method_name="tomography",
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
        },
        "required": ["exposure_ms", "n_projections", "angle_range_deg"],
    },
    practice_id=_PRACTICE_TOMO_ID,
    practice_name="2BM_tomography_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_TOMO_ID,
    plan_name="2BM_porous_media_tomography_plan",
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
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        # mount_subject
        e(),
        # define_method + schema
        *recipe_ladder_id_prefix(spec=_RECIPE),
        _RUN_ID,
        e(),
        # add_run_to_campaign (2 events)
        e(),
        e(),
        # start_campaign
        e(),
        # stop_run (Running -> Stopped)
        e(),
        # register_dataset (Trial; partial scan)
        _DATASET_ID,
        e(),
        # close_campaign
        e(),
    ]


@pytest.mark.integration
async def test_run_stop_early_lands_as_stopped_terminal(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate + intake + mount + recipe,
    start Run (planning 1500 projections), stop early (operator
    decides ~600 is sufficient), register partial Dataset. Assert
    Run reaches terminal Stopped with the reason captured."""
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
            reason="sample-of-opportunity quick look",
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

    await bind_start_run(deps)(
        StartRun(
            name="Sample-of-opportunity tomography (planning 1500 projections)",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; sample-of-opportunity look",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operator stops early: live-reco shows porosity features clearly -----

    await bind_stop_run(deps)(
        StopRun(
            run_id=_RUN_ID,
            reason=(
                "Live-reconstruction saturated at ~projection 600/1500; "
                "porosity features clearly resolved; remaining 900 "
                "projections would add noise more than signal for this "
                "sample-of-opportunity look. Stopping early to free "
                "beamtime for the next user."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Register partial-but-valid Dataset -----

    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Sample_of_opportunity_partial_600proj",
            uri=("file:///data/2026-05/Dr_PI/Sample_of_opportunity_partial_600proj.h5"),
            checksum_algorithm="sha256",
            checksum_value="c" * 64,
            byte_size=5_032_704_000,  # ~5 GB partial
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Run reached terminal Stopped (not Completed) -----

    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    assert run_event_types == [
        "RunStarted",
        "RunAddedToCampaign",
        "RunStopped",
    ]

    # ----- Assert: RunStopped carries the operator reason verbatim -----

    stopped_event = next(e for e in run_events if e.event_type == "RunStopped")
    assert "saturated" in stopped_event.payload["reason"]
    assert "sample-of-opportunity" in stopped_event.payload["reason"].lower()

    # ----- Assert: Dataset registered referencing the stopped Run -----

    dataset_events, _ = await deps.event_store.load("Dataset", _DATASET_ID)
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    dataset_payload = dataset_events[0].payload
    assert UUID(dataset_payload["producing_run_id"]) == _RUN_ID
    assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID
