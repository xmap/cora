"""Run.start cross-BC gate enforcement at APS 2-BM.

cluster: Staging
archetype: gate
bc_primary: Safety
bc_touches: Access, Campaign, Equipment, Recipe, Run, Safety, Subject

Scenario test for the Safety BC -> Run BC cross-BC integration:
`start_run` is HARD-GATED on the presence of an Active Safety
Clearance covering the Run's scope (Subject + Assets). Without
one, `RunRequiresActiveClearanceError` fires; with one, the Run
starts cleanly.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_safety_clearance_design]] for the gate
design lock.

## Why this scenario exists

The sibling scenario `test_2bm_proposal_clearance.py` walks the
Clearance FSM end-to-end inside the Safety BC. THIS scenario
exercises the cross-BC integration: the Run BC's `start_run`
decider reads a replicated projection of Clearance status
(`proj_safety_clearance_summary` via the `PostgresClearanceLookup`
adapter) and refuses to start a Run if no Active Clearance
references the Run's scope.

Until this scenario, the existing `test_2bm_*` scenarios all used
the test-default `AlwaysCoveredClearanceLookup` stub which bypasses
the gate. This is the FIRST scenario to inject
`PostgresClearanceLookup` and exercise the real gate. It surfaces:

  - The two-phase failure semantics: "no clearance at all"
    (`RunRequiresActiveClearanceError`) vs "clearance exists but
    none Active" (`RunClearanceCoverageMismatchError`). This
    scenario covers the first; the second is a watch item for a
    sibling scenario.
  - The projection-bookmark interplay: Safety BC must drain its
    projection (`proj_safety_clearance_summary`) before the gate
    sees the Active row. The `drain_projections` helper from the
    projection-worker test infrastructure is the canonical bridge.
  - The Subject-binding pathway: a Clearance bound to the Subject
    via `SubjectBinding` covers ANY Run on that Subject (the gate
    matches on the union of Subject + Asset + Run-id bindings).
    This scenario uses Subject-binding (matches the
    `test_2bm_proposal_clearance.py` shape).

## Domain shape (operator narrative)

  1. Coordinator opens beamtime intake (PI + Subject + Campaign).
  2. Operator mounts the sample + defines the recipe ladder.
  3. Operator attempts to start a Run -- **rejected** because no
     Active Clearance covers the Subject.
  4. Beamline Scientist + Coordinator walk the ESAF through the
     full FSM (Defined -> Submitted -> UnderReview -> Approved
     -> Active).
  5. Safety projection drains; `proj_safety_clearance_summary`
     now carries the Active row referencing the Subject.
  6. Operator retries start_run -- **succeeds**, Run enters
     Running, scan proceeds.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The pure Safety
FSM walk (proposal_clearance) and the Run.start gate enforcement
are separable concerns:

  - The FSM walk has no cross-BC dependency; it stays inside the
    Safety BC and is a clean source-of-truth for "the Safety
    workflow itself".
  - The gate enforcement requires the cross-BC projection +
    `PostgresClearanceLookup` adapter + the Run BC's
    `start_run` decider. It's a different test surface.

Bundling would conflate the two and obscure both diagnostics.

## What this scenario surfaces (gap-finding intent)

  - **Operator UX for first-Run-after-intake.** A real 2-BM
    operator would never type `start_run` before the ESAF
    activates -- the LIMS UI gates the form. CORA's gate fires
    at the aggregate level as a safety net; the UI layer is
    upstream-responsible. Whether the gate error message is
    operator-friendly enough is a watch item.
  - **The CoverageMismatch failure mode is NOT exercised here.**
    `RunClearanceCoverageMismatchError` fires when a Clearance
    references the Run's scope but is NOT Active (eg. Expired
    or Superseded). A sibling scenario should cover this (after
    `expire_clearance` or `amend_clearance` lands at scenario
    tier).
  - **No assertion that the projection bookmark advanced.** The
    `drain_projections` helper waits for the bookmark to catch up,
    but the assertion is implicit (the gate retry succeeding =
    proof that the projection saw Active). If a future projection-
    visibility regression hides Active rows, this scenario would
    surface it indirectly.
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
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run.aggregates.run import RunRequiresActiveClearanceError
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.safety._projections import register_safety_projections
from cora.safety.adapters import PostgresClearanceLookup
from cora.safety.aggregates.clearance import (
    SubjectBinding,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features.activate_clearance import ActivateClearance
from cora.safety.features.activate_clearance import bind as bind_activate_clearance
from cora.safety.features.append_clearance_review_step import AppendClearanceReviewStep
from cora.safety.features.append_clearance_review_step import (
    bind as bind_append_review_step,
)
from cora.safety.features.approve_clearance import ApproveClearance
from cora.safety.features.approve_clearance import bind as bind_approve_clearance
from cora.safety.features.register_clearance import RegisterClearance
from cora.safety.features.register_clearance import bind as bind_register_clearance
from cora.safety.features.start_clearance_review import StartClearanceReview
from cora.safety.features.start_clearance_review import bind as bind_start_review
from cora.safety.features.submit_clearance import SubmitClearance
from cora.safety.features.submit_clearance import bind as bind_submit_clearance
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import (
    BEAMLINE_SCIENTIST_ACTOR_ID,
    operator_for,
)
from tests.integration.scenarios._tomography_fixture import (
    RecipeSpec,
    TomographyAssetIds,
    define_recipe_ladder,
    install_and_activate_tomography_assets,
    recipe_ladder_id_prefix,
    tomography_install_id_prefix,
)

_NOW = datetime(2026, 5, 18, 1, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000441bb")

# Scenario tag: 441 (safety ops / Run.start gate enforcement).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000441501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000441a01")

_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000441c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000441c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000441c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000441c31")

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000441a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000441a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000441a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000441a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000441b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000441b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000441b21")
# Reviewer Actor (`BEAMLINE_SCIENTIST_ACTOR_ID`) is registered by
# `install_aps_unit` (canonical fixture-owned UUID).
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000441f01")
_ESAF_TEMPLATE_ID = ClearanceTemplateId(clearance_template_stream_id("cora", "ESAF"))
_METHOD_ID = UUID("01900000-0000-7000-8000-000000441d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d39f")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000441d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000441d21")
_RUN_ID = UUID("01900000-0000-7000-8000-000000441f02")

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
    method_id=_METHOD_ID,
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
    practice_id=_PRACTICE_ID,
    practice_name="2BM_tomography_practice",
    site_id=_APS_SITE_ID,
    plan_id=_PLAN_ID,
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
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    The first start_run attempt is REJECTED by the gate before any
    event is emitted (decider raises before the handler appends),
    so it consumes NO ids. Only the successful start_run later
    consumes its run_id + event_id slot.
    """
    e = uuid4
    return [
        *tomography_install_id_prefix(asset_ids=_TOMO_ASSETS),
        *beamtime_id_prefix(spec=_BEAMTIME),
        # mount_subject
        e(),
        # define_method + schema
        *recipe_ladder_id_prefix(spec=_RECIPE),
        # though the decider raises and no event is emitted. (Event-id
        # is NOT consumed; only the run_id allocation runs first.)
        e(),  # consumed by the failed start_run's id_generator.new_id()
        # register_clearance + walk to Active (7 events)
        _CLEARANCE_ID,
        e(),  # register
        e(),  # submit
        e(),  # start_review
        e(),  # append_step
        e(),  # approve
        e(),  # activate
        # start_run (the successful retry; the first attempt raises before allocating)
        _RUN_ID,
        e(),
        # add_run_to_campaign (2 events; cross-stream atomic)
        e(),
        e(),
        # start_campaign
        e(),
        # complete_run
        e(),
        # close_campaign
        e(),
    ]


async def _drain_safety_projections(db_pool: asyncpg.Pool) -> None:
    """Drain the Safety BC's projection so the PostgresClearanceLookup
    can see Active rows."""
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_run_start_blocked_then_unblocked_by_clearance_activation(
    db_pool: asyncpg.Pool,
) -> None:
    """First start_run fires before any Clearance covers the Subject:
    expect RunRequiresActiveClearanceError. Walk the Clearance through
    the full FSM to Active, drain the Safety projection, retry
    start_run: expect success. Assert both the rejection and the
    eventual Run reaching Completed."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=_id_queue(),
        clearance_lookup=PostgresClearanceLookup(db_pool),
    )
    # Seed the in-memory ClearanceTemplateLookup with an Active "ESAF"
    # template in the "cora" facility so register_clearance's cross-
    # aggregate template lookup resolves before the decider runs.
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_ESAF_TEMPLATE_ID,
        facility_code="cora",
        code="ESAF",
        status="Active",
        version=1,
    )

    # ----- Facility hierarchy + beamtime intake -----

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
            reason="gated-start scenario setup",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Recipe ladder -----

    await define_recipe_ladder(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_RECIPE,
    )

    # ----- Operator attempts start_run BEFORE any Clearance exists -----
    # Gate fires at the decider; no Run event is appended, so the queued
    # _RUN_ID + event_id stay in the queue for the later successful retry.

    start_run_cmd = StartRun(
        name="Proposal 2026-1234 sample A first scan",
        plan_id=_PLAN_ID,
        subject_id=_SUBJECT_ID,
        override_parameters={
            "exposure_ms": 100,
            "n_projections": 1500,
            "angle_range_deg": 180.0,
        },
        trigger_source="operator-manual; PI present; pre-clearance attempt",
    )

    with pytest.raises(RunRequiresActiveClearanceError):
        await bind_start_run(deps)(
            start_run_cmd,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Register + walk the ESAF Clearance to Active -----
    # Reviewer (BS) is the canonical Actor registered by `install_aps_unit`.

    subject_binding = SubjectBinding(subject_id=_SUBJECT_ID)

    await bind_register_clearance(deps)(
        RegisterClearance(
            template_id=_ESAF_TEMPLATE_ID,
            facility_code="cora",
            title="Proposal 2026-1234 ESAF (porous sandstone tomography)",
            bindings=frozenset({subject_binding}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_submit_clearance(deps)(
        SubmitClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start_review(deps)(
        StartClearanceReview(
            clearance_id=_CLEARANCE_ID,
            first_reviewer_role="BeamlineScientist",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_append_review_step(deps)(
        AppendClearanceReviewStep(
            clearance_id=_CLEARANCE_ID,
            step_index=0,
            role="BeamlineScientist",
            actor_id=BEAMLINE_SCIENTIST_ACTOR_ID,
            decision="Approved",
            decided_at=_NOW,
            notes="LGTM",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_approve_clearance(deps)(
        ApproveClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_activate_clearance(deps)(
        ActivateClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Drain Safety projections so PostgresClearanceLookup sees the
    # Active row in proj_safety_clearance_summary.
    await _drain_safety_projections(db_pool)

    # ----- Retry start_run: now the gate passes -----

    await bind_start_run(deps)(
        start_run_cmd,
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

    # ----- Assert: Run reached terminal Completed (gate let it through) -----

    run_events, _run_version = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    assert "RunStarted" in run_event_types
    assert "RunAddedToCampaign" in run_event_types
    assert "RunCompleted" in run_event_types

    # ----- Assert: Campaign FSM exercised cleanly -----

    campaign_events, _ = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    campaign_event_types = [e.event_type for e in campaign_events]
    assert "CampaignStarted" in campaign_event_types
    assert "CampaignClosed" in campaign_event_types
