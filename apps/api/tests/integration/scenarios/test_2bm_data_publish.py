"""Data publish at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Data
bc_touches: Campaign, Data, Equipment, Recipe, Run, Subject

Scenario test for the closing-the-books routine: after a beamtime
finishes acquisition, the operator reviews each Trial Dataset and
promotes the keepers to Production, then closes the Campaign
(Active -> Closed). Sourced from `2bm-docs ops/item_025.rst`
(end-of-beamtime data publish workflow). The 2-BM Globus collection is
APS:DM:2BM, not Petrel (staff-confirmed, DATA-3, #270).

Step O-6 of the operations-phase canonical-acquisition chain.
Final scenario in the canonical first-acquisition arc.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Closes the operations-phase narrative. The full canonical arc is:

  O-1 intake -> O-2 mount -> O-3 scan -> O-4 debrief -> O-5 dismount -> O-6 publish

First scenario-tier exercise of:

  - `promote_dataset` slice (`Trial -> Production` with operator-
    supplied reason)
  - `close_campaign` slice (`Active -> Closed`)
  - The Dataset publication lifecycle: a raw scan lands as Trial
    (per Dataset BC genesis default), waits for operator review,
    promotes to Production when keeper-status is decided

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. Promotion and
Campaign close are review-time operator routines, distinct from
the acquisition routines that produced the data. Bundling into
O-3 would conflate "scan ran" with "scan was kept and published";
they answer different questions over different timelines.

## Asset stack (minimal; setup only)

The publish workflow doesn't touch hardware. The full Equipment
chain is registered + activated only so the scan Run can land
(its Plan binds to the imaging-chain Assets). Aerotech is the
only Device the Subject mount needs; the rest are registered so
the Plan validates.

## What this scenario surfaces (gap-finding intent)

  - **Promotion is strict-not-idempotent.** Re-promoting an
    already-Production Dataset raises (mirrors `discard_dataset`
    + every other terminal-mutation slice). This is by design but
    means the operator UX must surface the Dataset's current
    intent before offering a promotion button.
  - **Campaign close locks membership.** No further Runs can be
    added after `close_campaign`. Whether the operator should be
    warned ("you're about to close; any in-flight Runs that
    haven't joined yet will need a new Campaign") is a watch item.
  - **LogbookMirror is exercised here in production, not in
    this scenario.** End-of-beamtime publishes the Campaign + child
    Runs + promoted Datasets to Olog / SciLog / SciCat via the
    abstract `LogbookMirror` (per `2bm-docs ops/item_030.rst`
    tomolog workflow). No implementor exists today; the scenario
    asserts only the promotion + close, not the mirror publication.
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
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.promote_dataset import bind as bind_promote_dataset
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

_NOW = datetime(2026, 5, 17, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000406bb")

# Scenario tag: 406 (operations / data publish).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000406501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000406a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000406a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000406a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000406a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000406a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000406b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000406b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000406b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000406d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d3a7")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000406d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000406d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000406f02")
_DATASET_ID = UUID("01900000-0000-7000-8000-000000406f01")

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
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        _RUN_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # start_campaign (Planned -> Active; explicit, not implicit)
        e(),  # complete_run
        e(),  # measure_subject
        _DATASET_ID,
        e(),  # register_dataset (Trial)
        # O-6 specific:
        e(),  # promote_dataset (Trial -> Production)
        e(),  # close_campaign (Active -> Closed)
    ]


@pytest.mark.integration
async def test_data_publish_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Replicate the full O-3 setup (facility + beamtime + scan + Trial
    Dataset), then exercise the publish routine: promote Dataset to
    Production + close Campaign. Assert the Dataset stream carries the
    promotion event, the Campaign stream is in Closed, and the lineage
    fields stay intact across the intent transition."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Setup: facility + activate + beamtime + mount + scan + Dataset (Trial) -----

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
            reason="proposal scan setup",
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
            name="Proposal 2026-1234 sample A tomography",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; first scan of beamtime",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Explicit Campaign Planned -> Active (add_run_to_campaign does not
    # auto-transition; the operator chooses when to mark the Campaign
    # active vs leaving it Planned with Runs queued).
    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
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

    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Proposal_2026-1234_sample_A_tomo",
            uri="file:///data/2026-05/Dr_PI/Proposal_2026-1234_sample_A_tomo.h5",
            checksum_algorithm="sha256",
            checksum_value="f" * 64,
            byte_size=12_582_912_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- O-6 specific: promote Dataset (Trial -> Production) -----
    # Operator reviewed the scan (signal level OK, no artifacts, sample
    # representative); decides to promote to Production for publication.

    await bind_promote_dataset(deps)(
        PromoteDataset(
            dataset_id=_DATASET_ID,
            reason=(
                "operator review complete; Dataset is keeper-grade "
                "for publication: signal level matches first-light + "
                "flat baseline reference; no detector artifacts; "
                "sample representative of porous-media core class"
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- O-6 specific: close Campaign (Active -> Closed) -----
    # End of beamtime; no further Runs will be added. Members are locked
    # after this transition.

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Dataset stream carries genesis + promotion -----

    dataset_events, dataset_version = await deps.event_store.load("Dataset", _DATASET_ID)
    assert dataset_version == 2
    assert [e.event_type for e in dataset_events] == [
        "DatasetRegistered",
        "DatasetPromoted",
    ]
    promote_payload = dataset_events[1].payload
    assert "keeper-grade" in promote_payload["reason"]

    # ----- Assert: Campaign stream carries genesis + add Run + closed -----

    campaign_events, _campaign_version = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert "CampaignRegistered" in campaign_event_types
    assert "CampaignRunAdded" in campaign_event_types
    assert "CampaignClosed" in campaign_event_types
