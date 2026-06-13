"""RunDebriefer on a DegradedCompletion Run at APS 2-BM.

cluster: Advisories
archetype: agent
bc_primary: Decision
bc_touches: Campaign, Decision, Equipment, Recipe, Run, Subject

Sibling scenario to `test_2bm_run_debriefer.py` (the happy-path
`NominalCompletion` variant): exercises the RunDebriefer agent on a
Run that completed with operator intervention (mid-flight Asset
degrade/restore cycle). The agent emits a `DegradedCompletion`
Decision capturing the imperfect-but-successful narrative.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_run_debrief_design]] for the agent design
lock + 5-value choice taxonomy.

## Why this scenario exists

**First scenario-tier exercise of the agent on a non-happy-path
Run.** The happy-path `NominalCompletion` was exercised in O-4.
The agent's real value (correctly framing imperfect outcomes,
flagging operator interventions in the AAR narrative) only shows
up on non-happy-path Runs.

Three of the five `DecisionChoice` values are non-happy-path:
`DegradedCompletion` / `OperatorAbort` / `EquipmentAbort` /
`DataSuspect`. This scenario covers `DegradedCompletion`; the
sibling `test_2bm_run_debrief_aborted.py` covers `EquipmentAbort`.

## Domain shape (operator narrative)

  1. Scan starts at normal parameters.
  2. Mid-flight, operator observes alignment drift (Aerotech
     bearing showing intermittent encoder jitter).
  3. Operator marks `Aerotech_ABRS_rotary` condition `Degraded`
     with a reason (the audit trail records the intervention).
  4. Operator pauses long enough to verify the encoder reseats;
     no formal fix beyond letting it settle.
  5. Operator marks the Asset `Restored` to `Nominal` and the
     scan continues to completion.
  6. Run reaches `Completed` normally.
  7. Agent observes the terminal `RunCompleted` event, loads
     context including the Asset stream's degrade/restore pair,
     and emits `DegradedCompletion` Decision (the canned LLM
     response in this scenario simulates the agent making that
     classification).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The happy-path
debrief (O-4) and the degraded debrief are separable: different
operator narrative, different agent decision, different Asset
event history, different LLM input shape. Bundling would conflate
"agent emits a Decision" with "agent classifies outcome
correctly".

## What this scenario surfaces (gap-finding intent)

  - **Agent read scope today excludes Asset stream.** Per
    [[project_run_debrief_design]] v1 read scope is
    Run+Observation+Verdict+Subject+Plan+Method+Practice+
    Cautions. The Asset stream's degrade/restore events would be
    in scope only if a Caution gets registered (which is the
    operator's downstream action when an intervention recurs).
    Whether expanding read scope to include the Asset stream is
    needed for richer narratives is a watch item.
  - **The agent's classification is not validated here.** The
    canned LLM returns `DegradedCompletion` regardless of input;
    real-life quality (does the agent correctly distinguish
    Nominal from Degraded based on read-scope context?) needs
    recorded-cassette or quality-eval tracks (deferred per the
    design memo's ConfidenceCalibrator trigger).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, seed_run_debriefer_agent
from cora.agent.subscribers.run_debriefer import (
    RunDebrieferSubscriber,
    _derive_decision_id,
)
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign import bind as bind_add_run_to_campaign
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.degrade_asset import DegradeAsset
from cora.equipment.features.degrade_asset import bind as bind_degrade_asset
from cora.equipment.features.restore_asset import RestoreAsset
from cora.equipment.features.restore_asset import bind as bind_restore_asset
from cora.infrastructure.ports import FakeLLM, FakeLLMResponse
from cora.infrastructure.ports.event_store import StoredEvent
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
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

_NOW = datetime(2026, 5, 17, 18, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000420bb")

# Scenario tag: 420 (operations / debrief variant: DegradedCompletion).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000420501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000420a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000420a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000420a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000420a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000420a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000420b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000420b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000420b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000420d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d577")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000420d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000420d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000420f02")

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
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, degraded run)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime (degraded)",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
)

_CANNED_DEGRADED_AAR = FakeLLMResponse(
    parsed={
        "choice": "DegradedCompletion",
        "confidence": 0.78,
        "reasoning": (
            "BLUF: Proposal 2026-1234 sample A scan completed with operator "
            "intervention; output Dataset is usable but flagged for downstream "
            "review. "
            "Synopsis: a single-Plan tomography Run on the mounted sandstone-core "
            "Subject ran to RunCompleted in the expected window, but mid-flight "
            "the Aerotech rotary stage was marked Degraded due to intermittent "
            "encoder jitter, then Restored to Nominal after a settle period. "
            "What was supposed to happen: complete the planned 1500-projection "
            "scan with no interventions. "
            "What actually happened: scan completed but with one degrade/restore "
            "cycle on the rotation axis. "
            "Why the difference: encoder jitter on a known Aerotech wear pattern; "
            "operator settle-and-resume was the appropriate response per the "
            "existing cold-start Caution playbook."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
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
        e(),  # mount_subject
        *recipe_ladder_id_prefix(spec=_RECIPE),
        _RUN_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # degrade_asset (mid-flight intervention)
        e(),  # restore_asset
        e(),  # complete_run
    ]


@pytest.mark.integration
async def test_run_debrief_agent_fires_on_degraded_completion(
    db_pool: asyncpg.Pool,
) -> None:
    """Exercise the agent on a Run that completed with mid-flight
    Asset degrade/restore intervention. Assert agent emits
    DegradedCompletion Decision."""
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
            reason="degraded-run scenario setup",
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
            name="Proposal 2026-1234 sample A tomography (with intervention)",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Mid-flight intervention: degrade and restore the Aerotech -----

    await bind_degrade_asset(deps)(
        DegradeAsset(
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason=(
                "intermittent encoder jitter observed at ~projection 600/1500; pausing for settle"
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_restore_asset(deps)(
        RestoreAsset(
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="encoder reseated after settle; resuming scan",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Agent fires on terminal RunCompleted; emits DegradedCompletion -----

    await seed_run_debriefer_agent(deps)

    run_events, _run_version = await deps.event_store.load("Run", _RUN_ID)
    terminal_events = [e for e in run_events if e.event_type == "RunCompleted"]
    assert len(terminal_events) == 1
    terminal_event = terminal_events[0]
    assert isinstance(terminal_event, StoredEvent)

    llm = FakeLLM(responses=[_CANNED_DEGRADED_AAR])
    subscriber = RunDebrieferSubscriber(
        event_store=deps.event_store,
        llm=llm,
        logbook_mirror=None,
    )
    await subscriber.apply(terminal_event, conn=None)

    # ----- Assert: Decision lands with DegradedCompletion choice -----

    decision_id = _derive_decision_id(terminal_event.event_id)
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "DegradedCompletion"
    assert decision.decided_by == RUN_DEBRIEFER_AGENT_ID

    # ----- Assert: Aerotech stream carries the degrade/restore pair -----

    aerotech_events, _ = await deps.event_store.load("Asset", _ASSET_AEROTECH_ABRS_ID)
    aerotech_event_types = [e.event_type for e in aerotech_events]
    assert "AssetDegraded" in aerotech_event_types
    assert "AssetRestored" in aerotech_event_types
