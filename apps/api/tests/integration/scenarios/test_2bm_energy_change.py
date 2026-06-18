"""Mid-beamtime energy change at APS 2-BM.

cluster: Runs
archetype: cycle
bc_primary: Decision
bc_touches: Campaign, Data, Decision, Equipment, Recipe, Run, Subject

Scenario test for the cross-Plan operator-decision shape: a
beamtime that begins at one X-ray energy, surfaces a need to
re-acquire at a different energy (contrast tuning, edge-of-
element work, sample-thickness reassessment), and proceeds with
a second Run on a different Plan whose default energy differs.

The pivot is captured as a `Decision(context="EnergyChange")`
authored by the on-shift operator (the principal Actor) so the
audit trail records WHO chose the switch, WHY, WHEN, and what
alternatives were considered.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_run_parameters_design]] for the
Method.schema → Plan.defaults → Run.overrides ladder this scenario
exercises across two distinct Plans.

## Why this scenario exists

The operations-phase corpus today exercises the agent-authored
Decision (RunDebriefer, O-4 + P2.1 + P2.2). The cross-Plan operator-
authored Decision is the symmetric shape: same `Decision`
aggregate, same `register_decision` slice, but the actor is a
human and the choice is a forward-looking acquisition pivot
rather than a backward-looking AAR.

This scenario exercises:

  - Two distinct `Plan`s under the same `Method` + `Practice`,
    differing only on their `default_parameters` (energy).
  - Per-Plan `update_plan_default_parameters` showing the
    Plan-defaults ladder is parameterizable per Plan instance.
  - A `Decision` written from a scenario test (not the agent
    subscriber pathway), `context="EnergyChange"`, with the
    operator principal as `actor_id`, `alternatives` carrying
    the two energies considered, `inputs` carrying the
    observed-contrast / required-edge metadata that drove the
    pivot.
  - Two child Runs in the same `Coordination` Campaign sharing
    Subject + Method but bound to different Plans.

## Domain shape (operator narrative)

  1. Beamtime opens; sample mounted on the rotation axis.
  2. Plan A (low-energy, ~25 keV) starts a Run; scan completes;
     a raw Dataset is registered.
  3. Operator inspects the projection contrast and concludes
     that the absorption edge of interest needs more flux at
     higher energy (~30 keV) to resolve the inclusion phase.
  4. Operator registers an `EnergyChange` Decision capturing
     the pivot: choice = "switch_to_30_keV"; reasoning =
     contrast-rationale + alternatives considered (stay at
     25 keV / switch to 30 keV / switch to 35 keV); the
     principal Actor is the decider.
  5. Plan B (high-energy, ~30 keV) starts a Run; scan completes;
     a second raw Dataset is registered.
  6. Subject reaches Measured once at the end.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The cross-Plan
operator-pivot shape exercises Decision authorship from a non-
agent source, and exercises multi-Plan use under one Subject /
Campaign. Bundling with the happy-path scan (O-3) would conflate
"how a single Run executes" with "how the operator pivots
between Runs"; bundling with the agent debrief (O-4) would
conflate the agent's read-only advisory authorship with the
operator's forward-looking acquisition authorship.

## What this scenario surfaces (gap-finding intent)

  - **Decision-to-Run linkage is not first-class.** The
    `EnergyChange` Decision precedes Run 2, and downstream
    consumers may want a fast lookup ("which Decision pivoted
    into this Run?"). Today the linkage lives in the operator's
    free-text reasoning + correlation_id; whether a structured
    field on Run (`decided_by_decision_id`, mirroring the
    `adjust_run` slice's [[project_adjust_run_design]] pattern)
    is needed for the start_run path is a watch item.
  - **Plan-defaults divergence audit.** Two Plans with identical
    Methods and Practices but distinct defaults have no
    higher-order grouping today; if a 2-BM scan-plan family
    grows to N>5 energy variants, a Plan-family projection
    (group by `(practice_id, asset_ids)` -> list of `(plan_id,
    default_parameters)`) becomes useful.
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
from cora.decision.aggregates.decision import (
    DecisionConfidenceSource,
    load_decision,
)
from cora.decision.features.register_decision import RegisterDecision
from cora.decision.features.register_decision import bind as bind_register_decision
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.recipe.aggregates.method import ExecutionPattern
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
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters import (
    bind as bind_update_plan_defaults,
)
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.shared.identity import ActorId
from cora.subject.features.measure_subject import MeasureSubject
from cora.subject.features.measure_subject import bind as bind_measure_subject
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

_NOW = datetime(2026, 5, 17, 21, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000423bb")

# Scenario tag: 423 (operations / energy_change).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000423a01")

# Opaque Practice-site UUID (the practice site, unrelated to Asset tier).
_PRACTICE_SITE_ID = UUID("01900000-0000-7000-8000-000000423501")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000423a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000423a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000423a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000423a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000423b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000423b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000423b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000423d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ef80")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000423d11")
_PLAN_LOW_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423d21")
_PLAN_HIGH_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423d22")

_RUN_LOW_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423f01")
_RUN_HIGH_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423f02")
_DATASET_LOW_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423f11")
_DATASET_HIGH_ENERGY_ID = UUID("01900000-0000-7000-8000-000000423f12")
_DECISION_PIVOT_ID = UUID("01900000-0000-7000-8000-000000423f21")

_DEVICES = (
    DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),
    DeviceSpec("SampleTop_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec("Scintillator", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID),
)

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1237 PI",
    subject_id=_SUBJECT_ID,
    subject_name="iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1237 multi-energy contrast study",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "tomography", "multi_energy", "porous_media"}),
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
        e(),  # activate_asset x 4
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        _METHOD_TOMO_ID,
        e(),  # define_method
        e(),  # update_method_parameters_schema
        _PRACTICE_TOMO_ID,
        e(),  # define_practice
        # Plan A (low energy)
        _PLAN_LOW_ENERGY_ID,
        e(),  # define_plan
        e(),  # update_plan_default_parameters (low)
        # Plan B (high energy)
        _PLAN_HIGH_ENERGY_ID,
        e(),  # define_plan
        e(),  # update_plan_default_parameters (high)
        e(),  # start_campaign (Planned -> Active; before any Run)
        # Run 1 (low energy) + dataset
        _RUN_LOW_ENERGY_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # complete_run
        _DATASET_LOW_ENERGY_ID,
        e(),  # register_dataset
        # Operator decides to pivot
        _DECISION_PIVOT_ID,
        e(),  # register_decision
        # Run 2 (high energy) + dataset
        _RUN_HIGH_ENERGY_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign
        e(),  # complete_run
        _DATASET_HIGH_ENERGY_ID,
        e(),  # register_dataset
        e(),  # measure_subject
        e(),  # close_campaign (Active -> Closed; beamtime arc complete)
    ]


@pytest.mark.integration
async def test_energy_change_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate, open Coordination Campaign,
    mount Subject, define two Plans differing on default energy,
    run Plan A's Run, register an EnergyChange Decision (operator
    pivot), run Plan B's Run, measure Subject. Assert the Decision
    landed with the right context + actor + choice, and both Runs
    completed cleanly."""
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
            reason="multi-energy pivot study; sample stays mounted across both Plans",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- One Method, one Practice, two Plans (differing on energy) -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.tomography",
        name="Tomography",
    )

    await bind_define_method(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="tomography",
            needed_family_ids=frozenset(
                {
                    _CAP_ROTARY_STAGE_ID,
                    _CAP_LINEAR_STAGE_ID,
                    _CAP_CAMERA_ID,
                    _CAP_SCINTILLATOR_ID,
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
                    "energy": {"type": "number", "minimum": 1, "maximum": 100},
                },
                "required": [
                    "exposure_ms",
                    "n_projections",
                    "angle_range_deg",
                    "energy",
                ],
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_multi_energy_practice",
            method_id=_METHOD_TOMO_ID,
            site_id=_PRACTICE_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_low_energy_plan",
            practice_id=_PRACTICE_TOMO_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_plan_defaults(deps)(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_LOW_ENERGY_ID,
            default_parameters_patch={
                "energy": 25.0,
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_high_energy_plan",
            practice_id=_PRACTICE_TOMO_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_plan_defaults(deps)(
        UpdatePlanDefaultParameters(
            plan_id=_PLAN_HIGH_ENERGY_ID,
            default_parameters_patch={
                "energy": 30.0,
                "exposure_ms": 150,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: Planned -> Active before any Run starts -----

    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Run 1: low-energy scan on Plan A -----

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1237 low-energy tomography (25 keV)",
            plan_id=_PLAN_LOW_ENERGY_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={},
            trigger_source="operator-manual; baseline scan at 25 keV",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_LOW_ENERGY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_LOW_ENERGY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Proposal_2026-1237_low_energy_25keV",
            uri="file:///data/2026-05/Dr_PI/Proposal_2026-1237_low_energy_25keV.h5",
            checksum_algorithm="sha256",
            checksum_value="a" * 64,
            byte_size=12_582_912_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_LOW_ENERGY_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operator decision: pivot to high energy -----

    await bind_register_decision(deps)(
        RegisterDecision(
            decided_by=ActorId(_PRINCIPAL_ID),
            context="EnergyChange",
            choice="switch_to_30_keV",
            reasoning=(
                "Low-energy (25 keV) projections show insufficient transmission "
                "through the iron-rich phase of the sandstone core; resolving the "
                "inclusion-phase contrast requires higher flux past the Fe K-edge. "
                "Switching beamline energy to 30 keV for the next Run; sample "
                "stays mounted."
            ),
            confidence=0.9,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(
                "stay_at_25_keV",
                "switch_to_30_keV",
                "switch_to_35_keV",
            ),
            inputs={
                "observed_transmission_pct_at_25keV": 12.5,
                "target_transmission_pct": 30.0,
                "phase_of_interest": "iron-bearing inclusion",
            },
            rule="operator:energy-pivot:v1",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Run 2: high-energy scan on Plan B -----

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1237 high-energy tomography (30 keV)",
            plan_id=_PLAN_HIGH_ENERGY_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={},
            trigger_source=("operator-manual; pivot from 25 keV per EnergyChange Decision"),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_HIGH_ENERGY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_HIGH_ENERGY_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_dataset(deps)(
        RegisterDataset(
            name="Proposal_2026-1237_high_energy_30keV",
            uri="file:///data/2026-05/Dr_PI/Proposal_2026-1237_high_energy_30keV.h5",
            checksum_algorithm="sha256",
            checksum_value="b" * 64,
            byte_size=12_582_912_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://www.nexusformat.org/NXtomo"}),
            producing_run_id=_RUN_HIGH_ENERGY_ID,
            subject_id=_SUBJECT_ID,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Subject Measured once after both Runs.
    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: close the multi-energy study (Active -> Closed) -----

    await bind_close_campaign(deps)(
        CloseCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: EnergyChange Decision landed with operator authorship -----

    decision = await load_decision(deps.event_store, _DECISION_PIVOT_ID)
    assert decision is not None
    assert decision.context.value == "EnergyChange"
    assert decision.choice.value == "switch_to_30_keV"
    assert decision.decided_by == _PRINCIPAL_ID
    assert decision.confidence_source is DecisionConfidenceSource.SELF_REPORTED
    assert decision.confidence == 0.9
    assert len(decision.alternatives) == 3

    # ----- Assert: both Runs reached terminal Completed -----

    for run_id in (_RUN_LOW_ENERGY_ID, _RUN_HIGH_ENERGY_ID):
        run_events, _ = await deps.event_store.load("Run", run_id)
        run_event_types = [e.event_type for e in run_events]
        assert "RunStarted" in run_event_types
        assert "RunAddedToCampaign" in run_event_types
        assert "RunCompleted" in run_event_types

    # ----- Assert: Campaign carries both member-add events -----

    campaign_events, _ = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert campaign_event_types.count("CampaignRegistered") == 1
    assert campaign_event_types.count("CampaignRunAdded") == 2
    assert campaign_event_types.count("CampaignStarted") == 1
    assert campaign_event_types.count("CampaignClosed") == 1

    # ----- Assert: each Dataset references its own producing_run_id -----

    for run_id, dataset_id in (
        (_RUN_LOW_ENERGY_ID, _DATASET_LOW_ENERGY_ID),
        (_RUN_HIGH_ENERGY_ID, _DATASET_HIGH_ENERGY_ID),
    ):
        dataset_events, dataset_version = await deps.event_store.load("Dataset", dataset_id)
        assert dataset_version == 1
        dataset_payload = dataset_events[0].payload
        assert UUID(dataset_payload["producing_run_id"]) == run_id
        assert UUID(dataset_payload["subject_id"]) == _SUBJECT_ID
