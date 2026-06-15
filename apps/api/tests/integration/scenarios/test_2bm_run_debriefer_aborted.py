"""RunDebriefer on an EquipmentAbort Run at APS 2-BM.

cluster: Advisories
archetype: agent
bc_primary: Decision
bc_touches: Campaign, Decision, Equipment, Recipe, Run, Subject

Sibling scenario to `test_2bm_run_debriefer.py` (NominalCompletion)
and `test_2bm_run_debrief_degraded.py` (DegradedCompletion):
exercises the RunDebriefer agent on a Run that terminated as
`Aborted` because an equipment fault made continuation
impossible. The agent emits an `EquipmentAbort` Decision capturing
the failed-scan narrative.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_run_debrief_design]] for the agent design
lock + 5-value choice taxonomy.

## Why this scenario exists

The agent's `DecisionChoice` taxonomy has five values; three are
non-happy-path. O-4 covered `NominalCompletion`; P2.1 covered
`DegradedCompletion`. This scenario covers `EquipmentAbort`, the
shape where an Asset fault forces the operator to abandon the
scan mid-flight rather than degrade-and-continue.

The distinguishing operator narrative: the fault is severe
enough that no settle/restore can recover the Run inside its
scan window. The audit trail must show (a) the Asset transitioning
to Faulted, (b) the Run terminating via `RunAborted` rather than
`RunCompleted`, and (c) the agent classifying the outcome as
equipment-caused (not operator-caused) abort.

## Domain shape (operator narrative)

  1. Scan starts at normal parameters; first ~600 of 1500
     projections complete cleanly.
  2. Hexapod sample-positioning controller locks up
     (`HexapodAllEnabled` stuck at 0): the canonical 2-BM fault
     captured by [[project_caution_design]] and exercised in the
     hexapod_reboot maintenance scenario.
  3. Operator marks Hexapod `Faulted` with the controller-lockup
     reason (audit-trail intervention).
  4. Operator cannot continue: hexapod needs full reboot
     ceremony (separate Procedure), and the Subject cannot stay
     mounted under a stuck rotation axis with no positioner.
  5. Operator aborts the Run with a free-text reason citing the
     hexapod fault.
  6. Run reaches `Aborted`.
  7. Agent observes the terminal `RunAborted` event, loads the
     Run, and emits `EquipmentAbort` Decision (the canned LLM
     response in this scenario simulates that classification).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The three debrief
variants (Nominal / Degraded / EquipmentAbort) exercise three
different terminal Run events, three different operator narratives,
three different LLM classifications. Bundling would conflate
"agent emits a Decision" with "agent picks the right choice for
each terminal-event shape".

## What this scenario surfaces (gap-finding intent)

  - **Distinguishing equipment-caused from operator-caused
    abort.** Both surface as `RunAborted` with a free-text
    `reason`; the agent must read the reason (and, future, the
    Asset stream) to classify between `EquipmentAbort` and
    `OperatorAbort`. v1 read scope per
    [[project_run_debrief_design]] is Run-only at the subscriber
    level, so the only signal the agent has today is the abort
    `reason` string. Whether that's enough is a watch item; the
    `OperatorAbort` variant is left to a future P2.x scenario.
  - **Cross-aggregate terminal-state coherence.** The Run reaches
    `Aborted` and the Hexapod Asset reaches `Faulted` in the same
    scenario; both are independent aggregates that the Decision's
    narrative ties together for the operator. The agent does not
    write to either stream — it advises via `DecisionRegistered`.
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
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.fault_asset import FaultAsset
from cora.equipment.features.fault_asset import bind as bind_fault_asset
from cora.infrastructure.ports import FakeLLM, FakeLLMResponse
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema import (
    bind as bind_update_method_schema,
)
from cora.run.features.abort_run import AbortRun
from cora.run.features.abort_run import bind as bind_abort_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 17, 19, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000421bb")

# Scenario tag: 421 (operations / debrief variant: EquipmentAbort).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000421501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000421a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))
_CAP_HEXAPOD_ID = family_stream_id(FamilyName("Hexapod"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000421a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000421a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000421a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000421a41")
_ASSET_HEXAPOD_ID = UUID("01900000-0000-7000-8000-000000421a51")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000421b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000421b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000421b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000421d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0e2be")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000421d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000421d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000421f02")

_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("SampleTop_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
    DeviceSpec("Hexapod", _ASSET_HEXAPOD_ID, "Hexapod", _CAP_HEXAPOD_ID),
)

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1235 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1235, sample B, aborted run)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1235 beamtime (aborted)",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
)

_CANNED_ABORTED_AAR = FakeLLMResponse(
    parsed={
        "choice": "EquipmentAbort",
        "confidence": 0.86,
        "reasoning": (
            "BLUF: Proposal 2026-1235 sample B scan terminated early at the "
            "operator's request after the Hexapod sample-positioning controller "
            "locked up; no usable Dataset was produced and the Subject will need "
            "remount once the hexapod reboot ceremony completes. "
            "Synopsis: a single-Plan tomography Run on the mounted sandstone-core "
            "Subject started cleanly and ran through approximately 600 of 1500 "
            "planned projections before the operator marked the Hexapod Faulted "
            "(HexapodAllEnabled stuck at 0) and aborted the Run. "
            "What was supposed to happen: complete the planned 1500-projection "
            "scan with no equipment intervention. "
            "What actually happened: the scan was aborted with a free-text reason "
            "citing the hexapod controller lockup; the Hexapod Asset transitioned "
            "to Faulted; the Run terminated via RunAborted rather than "
            "RunCompleted. "
            "Why the difference: a hardware-level fault on the hexapod positioner, "
            "not an operator-judgment or experimental-design issue; this is the "
            "canonical 2-BM lockup pattern that the hexapod_reboot Procedure "
            "exists to address. Classification: EquipmentAbort, not "
            "OperatorAbort, because the abort reason is causally downstream of "
            "the equipment fault rather than a free-standing operator decision."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


def _id_queue() -> list[UUID]:
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        e(),
        e(),
        e(),
        e(),
        e(),  # activate_asset x 5 (4 imaging + hexapod)
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        _METHOD_TOMO_ID,
        e(),  # define_method
        e(),  # update_method_parameters_schema
        _PRACTICE_TOMO_ID,
        e(),  # define_practice
        _PLAN_TOMO_ID,
        e(),  # define_plan
        _RUN_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # fault_asset (hexapod lockup)
        e(),  # abort_run
    ]


@pytest.mark.integration
async def test_run_debrief_agent_fires_on_equipment_abort(
    db_pool: asyncpg.Pool,
) -> None:
    """Exercise the agent on a Run that aborted due to a hexapod
    controller lockup. Assert agent emits EquipmentAbort
    Decision and the Hexapod stream carries the fault."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )

    for asset_id in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
        _ASSET_HEXAPOD_ID,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
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
            reason="aborted-run scenario setup",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.tomography",
        name="Tomography",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="tomography",
            needed_family_ids=frozenset(
                {
                    _CAP_ROTARY_STAGE_ID,
                    _CAP_LINEAR_STAGE_ID,
                    _CAP_CAMERA_ID,
                    _CAP_SCINTILLATOR_ID,
                    _CAP_HEXAPOD_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_method_schema(deps)(
        UpdateMethodParametersSchema(
            method_id=_METHOD_TOMO_ID,
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
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_tomography_practice",
            method_id=_METHOD_TOMO_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_porous_media_tomography_plan",
            practice_id=_PRACTICE_TOMO_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                    _ASSET_HEXAPOD_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1235 sample B tomography (aborted on hexapod fault)",
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

    # ----- Mid-flight equipment fault: Hexapod controller lockup -----

    await bind_fault_asset(deps)(
        FaultAsset(
            asset_id=_ASSET_HEXAPOD_ID,
            reason=(
                "controller lockup observed at ~projection 600/1500: "
                "2bmHXP:HexapodAllEnabled stuck at 0; scan cannot continue"
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operator aborts the Run (cannot continue under fault) -----

    await bind_abort_run(deps)(
        AbortRun(
            run_id=_RUN_ID,
            reason=(
                "hexapod fault: HexapodAllEnabled stuck at 0; no positioner "
                "control; aborting scan to run hexapod_reboot procedure"
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Agent fires on terminal RunAborted; emits EquipmentAbort -----

    await seed_run_debriefer_agent(deps)

    run_events, _run_version = await deps.event_store.load("Run", _RUN_ID)
    terminal_events = [e for e in run_events if e.event_type == "RunAborted"]
    assert len(terminal_events) == 1
    terminal_event = terminal_events[0]
    assert isinstance(terminal_event, StoredEvent)

    llm = FakeLLM(responses=[_CANNED_ABORTED_AAR])
    subscriber = RunDebrieferSubscriber(
        event_store=deps.event_store,
        llm=llm,
        logbook_mirror=None,
    )
    await subscriber.apply(terminal_event, conn=None)

    # ----- Assert: Decision lands with EquipmentAbort choice -----

    decision_id = _derive_decision_id(terminal_event.event_id)
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "EquipmentAbort"
    assert decision.decided_by == RUN_DEBRIEFER_AGENT_ID

    # ----- Assert: Hexapod stream carries the fault event -----

    hexapod_events, _ = await deps.event_store.load("Asset", _ASSET_HEXAPOD_ID)
    hexapod_event_types = [e.event_type for e in hexapod_events]
    assert "AssetFaulted" in hexapod_event_types
