"""Streaming tomography at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Run
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for TomoScanStream + tomoStream live-reconstruction:
the operator starts a tomography Run, observes the live-reconstructed
slice on tomoStream, decides mid-flight that exposure is too short
(noisy reconstruction), and issues `adjust_run` with a parameter
patch to bump `exposure_ms` without aborting. Sourced from `2bm-docs`
TomoScanStream + tomoStream workflow.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into. See [[project_adjust_run_design]]
for the adjust_run slice design lock.

## Why this scenario exists

**First scenario-tier exercise of the `adjust_run` slice** — the
mid-flight parameter-steering mechanism that distinguishes closed-
loop / autonomous-CT workflows from abort+restart. The slice is
exercised at unit + integration + contract tiers; this scenario
adds the operator-narrative tier (TomoScanStream feedback drives
operator decision to adjust).

Critical for CORA's autonomous-CT vision: the same `adjust_run`
pathway that an operator uses today is the pathway an Agent (or
operator-on-behalf-of-Agent) will use tomorrow. Establishing the
event shape end-to-end before agent integration lands is the
right ordering.

## Domain shape (synthesized from TomoScanStream + tomoStream)

  1. Operator starts a tomography Run with initial parameters
     (`exposure_ms`, `n_projections`, `angle_range_deg`).
  2. tomoStream renders a live-reconstructed slice continuously
     during the scan.
  3. Operator observes the reconstruction quality. If the slice
     is too noisy / saturated / off-center: decide to adjust.
  4. Issue `adjust_run` with a `parameters_patch` (RFC 7396 JSON
     Merge) targeting only the parameters needing change. The
     decider validates the merged result against the Method's
     `parameters_schema` (cross-BC STRICT anchor).
  5. Run continues; remaining projections acquire at the new
     parameter values.
  6. Complete Run, register live-reco snapshot as a Trial Dataset
     (intent stays Trial because the adjustment cycle's
     scientific validity needs operator review before publication).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The streaming
acquisition + mid-flight adjustment is a distinct operator
routine from the canonical static-parameters tomography (O-3).
Different rhythm (continuous feedback loop vs Plan-and-execute),
different output (live-reco snapshots vs raw projection stack as
keeper), different event shape (RunAdjusted vs no adjustment).

## Asset stack (full imaging chain)

Same as O-3: rotary + linear (Sample_top_X) + camera + scintillator.

## What this scenario surfaces (gap-finding intent)

  - **`adjust_run` is the abort+restart shortcut.** The old
    pattern was: see bad quality on live reco -> abort Run ->
    re-start with new parameters -> the audit log shows two
    Runs and no causation. `adjust_run` keeps one Run, one
    causation chain, one Dataset lineage, with the
    `RunAdjusted` event capturing the operator's mid-flight
    decision + reason + (optional) `decided_by_decision_id` link.
  - **`decided_by_decision_id` is None today.** In autonomous-CT
    futures, an Agent would emit a Decision (for example, "noise
    estimate above threshold; recommend bump exposure to 150ms")
    and the operator-or-agent action would `adjust_run` with
    that Decision id wired into `decided_by_decision_id`. This
    scenario uses None (operator-direct decision); the Agent-
    driven variant lands when an autonomous-control Agent is
    introduced.
  - **Live-reco snapshot intent stays Trial.** Even after the
    adjustment cycle completes successfully, the produced
    snapshot Dataset stays Trial pending operator post-run
    review. Promotion-to-Production lands in a separate
    `data_publish`-shape follow-on scenario.
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
from cora.run.features.adjust_run import AdjustRun
from cora.run.features.adjust_run import bind as bind_adjust_run
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

_NOW = datetime(2026, 5, 17, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000411bb")

# Scenario tag: 411 (operations / streaming tomography).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000411501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000411a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000411a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000411a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000411a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000411a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000411b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000411b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000411b21")

_METHOD_STREAM_ID = UUID("01900000-0000-7000-8000-000000411d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d606")
_PRACTICE_STREAM_ID = UUID("01900000-0000-7000-8000-000000411d11")
_PLAN_STREAM_ID = UUID("01900000-0000-7000-8000-000000411d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000411f02")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000411f01")

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
    subject_name="porous sandstone core (Proposal 2026-1234, sample A)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "streaming_tomography", "porous_media"}),
)


_RECIPE = RecipeSpec(
    capability_id=_CAPABILITY_ID,
    capability_code="cora.capability.tomography",
    capability_name="Tomography",
    method_id=_METHOD_STREAM_ID,
    method_name="streaming_tomography",
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
    practice_id=_PRACTICE_STREAM_ID,
    practice_name="2BM_streaming_tomography_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_STREAM_ID,
    plan_name="2BM_streaming_tomography_plan",
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
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        e(),  # start_campaign (Planned -> Active; before any Run)
        _RUN_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # adjust_run (mid-flight steering)
        e(),  # complete_run
        e(),  # measure_subject
        _DATASET_ID,
        e(),  # register_dataset (live-reco snapshot)
        e(),  # close_campaign (Active -> Closed; streaming session over)
    ]


@pytest.mark.integration
async def test_streaming_tomography_with_adjust_run(
    db_pool: asyncpg.Pool,
) -> None:
    """Start a streaming tomography Run, observe noisy live reco,
    adjust exposure_ms mid-flight without aborting, complete the Run,
    register the produced snapshot. Assert the Run stream carries
    RunAdjusted with the operator-supplied patch + reason."""
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
            reason="streaming-mode setup; sandstone core on kinematic tip",
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

    # ----- Campaign BC: Planned -> Active before any Run -----

    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Start Run with initial (under-exposed) parameters.
    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1234 sample A streaming tomography",
            plan_id=_PLAN_STREAM_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; streaming mode for live-reco feedback",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- O-streaming specific: operator sees noisy live reco; adjust exposure -----
    # tomoStream shows reconstruction noise above acceptable threshold around
    # projection ~300/1500. Operator decides to bump exposure_ms from 100 to 150
    # without aborting (mid-flight steering preserves single Run + lineage).

    await bind_adjust_run(deps)(
        AdjustRun(
            run_id=_RUN_ID,
            parameters_patch={"exposure_ms": 150},
            reason=(
                "tomoStream live reco showed noise level above acceptable "
                "threshold at ~projection 300/1500; bumping exposure from "
                "100ms to 150ms for remaining projections; no abort needed"
            ),
            decided_by_decision_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Run completes after the remaining projections at the adjusted exposure.
    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Live-reco snapshot Dataset lands as Trial (post-run review required for
    # Production promotion; see O-6 data_publish for that path).
    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Proposal_2026-1234_sample_A_streaming_snapshot",
            uri=("file:///data/2026-05/Dr_PI/Proposal_2026-1234_sample_A_streaming_snapshot.h5"),
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            byte_size=8_388_608_000,  # ~8 GB
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: close the streaming session (Active -> Closed) -----

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Run stream carries RunAdjusted with the patch + reason -----

    run_events, run_version = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    assert "RunStarted" in run_event_types
    assert "RunAdjusted" in run_event_types
    assert "RunCompleted" in run_event_types
    # RunStarted + RunAddedToCampaign + RunAdjusted + RunCompleted = 4
    assert run_version == 4

    adjust_events = [e for e in run_events if e.event_type == "RunAdjusted"]
    assert len(adjust_events) == 1
    adjust_payload = adjust_events[0].payload
    # adjust_run patch is recorded verbatim
    assert adjust_payload["parameters_patch"] == {"exposure_ms": 150}
    assert "tomoStream" in adjust_payload["reason"]
    assert "150ms" in adjust_payload["reason"]
    # No Decision link today (operator-direct decision; agent-driven variant
    # would populate decided_by_decision_id).
    assert adjust_payload.get("decided_by_decision_id") is None

    # ----- Assert: Subject lifecycle reached Measured -----

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
    ]

    # ----- Assert: Dataset registered as Trial with full cross-aggregate refs -----

    dataset_events, dataset_version = await deps.event_store.load("Dataset", _DATASET_ID)
    assert dataset_version == 1
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    dataset_payload = dataset_events[0].payload
    assert UUID(dataset_payload["producing_run_id"]) == _RUN_ID
    assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID

    # ----- Assert: Campaign FSM reached Closed via the explicit Started transition -----

    campaign_events, _ = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert "CampaignRegistered" in campaign_event_types
    assert "CampaignStarted" in campaign_event_types
    assert "CampaignRunAdded" in campaign_event_types
    assert "CampaignClosed" in campaign_event_types
