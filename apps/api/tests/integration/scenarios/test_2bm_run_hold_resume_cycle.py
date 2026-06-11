"""Hold + Resume cycle on a long Run at APS 2-BM.

cluster: Runs
archetype: fsm
bc_primary: Run
bc_touches: Campaign, Equipment, Recipe, Run, Subject

Scenario test for the operator-pause / operator-resume pathway:
a long tomography scan is in flight when the storage ring drops
beam (top-up gap, beam dump, or scheduled fill); the operator
pauses the Run, waits for beam return, and resumes. The Run then
completes normally with the pause captured as `RunHeld` +
`RunResumed` events in the audit trail.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. The hold/resume cycle is a bidirectional unlimited-
repeat pause matching PackML + Bluesky precedent (per
`hold_run/command.py`).

## Why this scenario exists

**First scenario-tier exercise of `hold_run` + `resume_run`.** The
Run BC's mid-lifecycle FSM has shipped 4 transition slices
(`hold_run` / `resume_run` / `stop_run` / `truncate_run`) but no
`test_2bm_*` scenario has exercised any of them. Three sibling
scenarios in this batch cover the four slices end-to-end:

  - THIS scenario: `hold_run` + `resume_run` (Running <-> Held
    bidirectional pause / unpause).
  - `test_2bm_run_stopped_early.py`: `stop_run` (controlled-exit
    terminal).
  - `test_2bm_run_truncated_after_outage.py`: `truncate_run`
    (retroactive cleanup for de-facto-dead Runs).

This scenario exercises:

  - `hold_run` (Running -> Held; no reason field on the command
    per the design lock: pause is a routine operation).
  - `resume_run` (Held -> Running; symmetric no-reason
    structure).
  - The cycle is unlimited-repeat-safe: the same Run may be
    held and resumed any number of times. This scenario
    demonstrates a single hold+resume but a future scenario
    could exercise N>1.

## Domain shape (operator narrative)

  1. Beamtime intake + sample mounted + recipe ladder defined.
  2. Operator starts a 1500-projection tomography scan.
  3. About 700 projections in, the storage ring drops beam
     (operator sees `S:SRCurrentAI` go to zero on the control-
     room feed).
  4. Operator pauses the Run via `hold_run` so the scan does not
     continue acquiring useless dark-only projections. The Run
     transitions Running -> Held.
  5. ~3 minutes later, beam is back. Operator confirms via the
     control-room feed.
  6. Operator resumes the Run via `resume_run`. The scan
     transitions Held -> Running and finishes the remaining
     ~800 projections.
  7. Run completes normally. The audit trail carries
     `RunStarted -> RunHeld -> RunResumed -> RunCompleted` plus
     the standard Campaign-membership events.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The hold/resume
cycle is a routine operator-pause concern distinct from:

  - Mid-flight parameter steering (`adjust_run`, exercised in
    `test_2bm_streaming_tomography.py`).
  - Mid-flight Asset condition changes
    (`degrade_asset`/`restore_asset`, exercised in
    `test_2bm_run_debrief_degraded.py`).
  - Terminal exits (Completed / Aborted / Stopped / Truncated).

Bundling would conflate "operator pauses for an external reason"
with "operator steers parameters" or "operator gives up on the
Run".

## What this scenario surfaces (gap-finding intent)

  - **`RunHeld` / `RunResumed` carry NO operator reason.** The
    operator's rationale for the pause lives only in
    correlation_id-tracing or a separate Decision aggregate
    (not exercised here). If beamtime audits ever require
    "why was this Run held at 09:32?", that traceability needs
    upstream wiring (a Decision authored by the operator with
    `context="RunHold"` or similar). Watch item.
  - **No projection-side aggregation of pause durations.** The
    Run's total wall-clock duration vs in-flight duration is
    computable from the event timestamps but no projection
    surfaces it today. A future RunDebriefer variant could
    consume this for a "data efficiency" metric in the AAR.
  - **The cycle does not gate Campaign membership or Dataset
    registration.** A Held Run is still a member of its Campaign
    and the post-Resume completion still produces a Dataset
    normally. No "held" status surfaces in downstream
    projections.
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
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.hold_run import HoldRun
from cora.run.features.hold_run import bind as bind_hold_run
from cora.run.features.resume_run import ResumeRun
from cora.run.features.resume_run import bind as bind_resume_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
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

_NOW = datetime(2026, 5, 18, 3, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000460bb")

# Scenario tag: 460 (run mid-lifecycle / hold + resume cycle).
# Future Run mid-lifecycle scenarios (stop, truncate) take 461..469.
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000460501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000460a01")

_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000460c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000460c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000460c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000460c31")

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000460a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000460a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000460a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000460a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000460b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000460b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000460b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000460d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0da84")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000460d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000460d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000460f02")

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
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, beam-trip pause)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime (with mid-flight pause)",
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
        # add_run_to_campaign (2 events; cross-stream atomic)
        e(),
        e(),
        # start_campaign
        e(),
        # hold_run (Running -> Held)
        e(),
        # resume_run (Held -> Running)
        e(),
        # complete_run
        e(),
        # close_campaign
        e(),
    ]


@pytest.mark.integration
async def test_run_hold_and_resume_cycle_completes_normally(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate + beamtime + mount + recipe,
    start Run, hold (beam trip), resume (beam back), complete.
    Assert RunHeld + RunResumed land between RunStarted and
    RunCompleted, and the Run reaches terminal Completed cleanly."""
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
            reason="hold/resume scenario setup",
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
            name="Proposal 2026-1234 sample A tomography (with beam-trip pause)",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; expecting full 1500 projections",
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

    # ----- Mid-flight pause: storage ring drops beam -----
    # Operator sees the control-room feed go dark on `S:SRCurrentAI`
    # at ~projection 700/1500; pauses to avoid acquiring useless
    # dark-only projections.

    await bind_hold_run(deps)(
        HoldRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Beam returns; operator resumes -----
    # ~3 minutes later, S:SRCurrentAI is back at nominal; operator
    # resumes the scan for the remaining ~800 projections.

    await bind_resume_run(deps)(
        ResumeRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Scan finishes; complete + close out -----

    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Run stream carries the full hold/resume cycle -----

    run_events, _run_version = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    # RunStarted + RunAddedToCampaign + RunHeld + RunResumed + RunCompleted = 5
    assert run_event_types == [
        "RunStarted",
        "RunAddedToCampaign",
        "RunHeld",
        "RunResumed",
        "RunCompleted",
    ]

    # ----- Assert: RunHeld + RunResumed carry no reason field (by design) -----

    held_event = next(e for e in run_events if e.event_type == "RunHeld")
    resumed_event = next(e for e in run_events if e.event_type == "RunResumed")
    assert "reason" not in held_event.payload
    assert "reason" not in resumed_event.payload
