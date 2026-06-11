"""Tomography scan at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Run
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for the canonical first user acquisition: with the
sandstone Subject mounted on the Aerotech kinematic tip, the
operator defines a tomography Method + Practice + Plan, starts a
Run, the Run completes, the Subject is marked Measured, and the
produced H5 projection stack is registered as a Production Dataset
joined to the Run + Subject + Campaign. Sourced from `2bm-docs`
TomoScan workflow + `pre_apsu/user/item_002.rst`.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Step O-3 of the operations-phase canonical-acquisition chain.
This is the LARGEST and most leverage-heavy operations scenario:
it exercises the Recipe ladder + Run lifecycle + Subject lifecycle
+ Dataset registration + Campaign membership cross-aggregate atomic
write, all end-to-end.

First exercise of:

  - `start_run` slice in a scenario (genesis of a Run aggregate)
  - `complete_run` slice (terminal Running -> Completed transition)
  - `measure_subject` slice (Subject Mounted -> Measured)
  - `register_dataset` with `producing_run_id` + `subject_id` set
    (Production intent; first non-calibration Dataset in the corpus)
  - `add_run_to_campaign` cross-aggregate atomic two-stream write
    (Campaign Planned -> Active via the implicit transition once a
    Run joins)

Also the 3rd operations scenario that re-uses the intake setup
(beamtime_intake genesis registrations), triggering the
`_beamtime_fixture.py` extraction by rule-of-three.

## Why a separate scenario (not bundled into `first_proposal_scan`)

Per [scenarios/README.md](../README.md) Rule 1. The scan is the
acquisition routine; mount (O-2) is the pre-acquisition routine;
intake (O-1) opens the beamtime context. Each is separable.

## Asset stack (the full imaging chain)

Tomography needs the rotation axis + sample-X correction motor +
detector chain (camera + scintillator). All four Devices register
and activate before the scan starts. The shutter is omitted (this
scenario assumes the beam is open via first_light / commissioning
ceremony pre-conditions; opening the shutter is not part of the
scan routine itself).

## What this scenario surfaces (gap-finding intent)

  - **Run override_parameters is the first cross-BC schema-validated
    payload exercise.** Operator-supplied `exposure_ms`,
    `n_projections`, `angle_range_deg` merge with Plan's
    `default_parameters` via RFC 7396 + validate against the bound
    Method's `parameters_schema` (cross-BC schema-validated values
    pattern). Today the Plan has empty defaults so override is the
    whole payload; once Methods grow real parameters schemas,
    `trigger_source` becomes the audit trail for why an operator
    deviated from defaults.
  - **`add_run_to_campaign` is the first multi-stream atomic in
    scenarios.** The Campaign FSM does NOT auto-promote on first
    member join: `Planned` accepts Runs, but `Planned -> Active`
    requires an explicit `start_campaign` call (per the Campaign
    design memo). This scenario calls `start_campaign` before
    `add_run_to_campaign` so the Campaign actually enters Active
    once a Run is bound, matching real-beamtime narrative where
    the operator declares "campaign is live" before bringing Runs
    in.
  - **Dataset registration order matters for lineage.** The Dataset
    must register AFTER the Run completes (the integrity guard
    requires `producing_run_id` to point to a Run in a terminal
    state for Production intent). Whether the register_dataset
    handler should auto-detect "Run not yet complete" and surface
    a friendlier error than the generic state mismatch is a watch
    item.
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

_NOW = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000403bb")

# Facility. Scenario tag: 403 (operations / tomography scan).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000403501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000403a01")

# Capabilities (full imaging chain)
_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000403c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000403c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000403c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000403c31")

# Devices (full imaging chain)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000403a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000403a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000403a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000403a41")

# Beamtime (intake) aggregates
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000403b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000403b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000403b21")

# Recipe ladder
_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000403d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d508")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000403d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000403d21")

# Run + Dataset (f-tagged; f02 avoids clashing with the f01 Dataset tag).
_RUN_ID = UUID("01900000-0000-7000-8000-000000403f02")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000403f01")

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
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
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
            "exposure_ms": {
                "type": "integer",
                "minimum": 1,
                "unit": {"system": "ucum", "code": "ms"},
            },
            "n_projections": {"type": "integer", "minimum": 1},
            "angle_range_deg": {
                "type": "number",
                "minimum": 1,
                "maximum": 360,
                "unit": {"system": "ucum", "code": "deg"},
            },
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
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        # Beamtime intake: actor + subject + campaign (3 pairs = 6 ids)
        *beamtime_id_prefix(spec=_BEAMTIME),
        # mount_subject: event_id only
        e(),
        # Recipe ladder: Method + schema + Practice + Plan (7 ids with schema)
        *recipe_ladder_id_prefix(spec=_RECIPE),
        # start_run: run_id, event_id
        _RUN_ID,
        e(),
        # add_run_to_campaign (cross-aggregate atomic; 2 event ids for the 2 streams)
        e(),  # CampaignRunAdded
        e(),  # RunAddedToCampaign
        # start_campaign: event_id (explicit Planned -> Active)
        e(),
        # complete_run: event_id
        e(),
        # close_campaign: event_id (Active -> Closed)
        e(),
        # measure_subject: event_id
        e(),
        # register_dataset: dataset_id, event_id
        _DATASET_ID,
        e(),
    ]


@pytest.mark.integration
async def test_tomography_scan_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate, open the beamtime + mount
    the Subject, define the tomography Recipe ladder, start the Run,
    add to Campaign (atomic), complete the Run, mark Subject Measured,
    register the Production projection stack as a Dataset joined to
    Run + Subject. Assert the full event sequence + cross-aggregate
    references resolve."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed full imaging chain (4 Devices) + activate all of them -----

    await install_and_activate_tomography_assets(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        asset_ids=_TOMO_ASSETS,
    )

    # ----- Open beamtime via fixture (PI Actor + Subject + Campaign) -----

    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    # ----- Subject BC: mount on the Aerotech kinematic tip -----

    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=_SUBJECT_ID,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="first proposal scan; sandstone core sample A on kinematic tip",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe BC: Method + parameters_schema + Practice + Plan via fixture -----
    # Declares the tomography Method's parameters_schema (operator-facing
    # exposure/projection-count/angle-range) so start_run accepts the
    # override_parameters below, per the STRICT validation posture in
    # [[project_schema_validated_values_pattern]].

    await define_recipe_ladder(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_RECIPE,
    )

    # ----- Run BC: start the scan -----
    # Override parameters carry operator-supplied exposure + projections +
    # angle range. Plan has empty default_parameters today; once Methods grow
    # parameters_schema, these override the defaults via RFC 7396 merge.

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1234 sample A tomography (first proposal scan)",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; PI present; first scan of beamtime",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: add the Run to the Campaign (cross-aggregate atomic) -----
    # Two-stream atomic write: Campaign gets CampaignRunAdded + Run gets
    # RunAddedToCampaign. The Campaign FSM does NOT auto-promote; Planned
    # accepts Runs but stays Planned until an explicit start_campaign.

    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Explicit Planned -> Active. The operator declares the Campaign live
    # once at least one Run has joined.
    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Run BC: complete the Run (Running -> Completed) -----

    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: close the Campaign (Active -> Closed) -----
    # Single-Run scan completes the beamtime arc; close locks membership.

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Subject BC: mark Measured (Mounted -> Measured) -----
    # Aggregate-level "has been measured at least once". Per-measurement detail
    # (frame count, params, results) lives in Run + Dataset.

    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Data BC: register the produced H5 projection stack as a Dataset -----
    # Production intent; producing_run_id + subject_id both set; NeXus NXtomo
    # profile. Real 2-BM file path pattern: /data/YYYY-MM/PI_dir/file.h5.

    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Proposal_2026-1234_sample_A_tomo",
            uri="file:///data/2026-05/Dr_PI/Proposal_2026-1234_sample_A_tomo.h5",
            checksum_algorithm="sha256",
            checksum_value="f" * 64,  # placeholder; real checksum at acquisition
            byte_size=12_582_912_000,  # ~12 GB for a typical micro-CT stack
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Subject stream carries genesis + mount + measure -----

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
    ]

    # ----- Assert: Run stream lifecycle (start + campaign-assign + complete) -----

    run_events, run_version = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    assert "RunStarted" in run_event_types
    assert "RunAddedToCampaign" in run_event_types
    assert "RunCompleted" in run_event_types
    # Run version reflects the 3 events that landed on the Run stream
    assert run_version == 3

    # ----- Assert: Campaign membership (Planned -> Active via implicit transition) -----

    campaign_events, _campaign_version = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert "CampaignRegistered" in campaign_event_types
    assert "CampaignRunAdded" in campaign_event_types
    assert "CampaignStarted" in campaign_event_types
    assert "CampaignClosed" in campaign_event_types

    # ----- Assert: Dataset registered with full cross-aggregate refs -----

    dataset_events, dataset_version = await deps.event_store.load("Dataset", _DATASET_ID)
    assert dataset_version == 1
    assert [e.event_type for e in dataset_events] == ["DatasetRegistered"]
    dataset_payload = dataset_events[0].payload
    assert dataset_payload["name"] == "Proposal_2026-1234_sample_A_tomo"
    # Dataset lands in Trial intent; promote_dataset (O-6) transitions to Production.
    assert UUID(dataset_payload["producing_run_id"]) == _RUN_ID
    assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID
    assert dataset_payload["encoding"]["media_type"] == "application/x-hdf5"
    assert "https://www.nexusformat.org/NXtomo" in dataset_payload["encoding"]["conforms_to"]
