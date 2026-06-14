"""Proposal-clearance FSM walk at APS 2-BM.

cluster: Staging
archetype: fsm
bc_primary: Safety
bc_touches: Access, Safety

Scenario test for the Safety BC's full Clearance lifecycle in a
beamtime-intake context: a proposal arrives, an ESAF
(Experiment Safety Assessment Form) is registered against the
proposal Subject + self-Facility code, walks through the standard
2-step review chain (Beamline Scientist + ESRB), gets approved, and
activates ready for the first Run to bind against.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_safety_clearance_design]] for the design
lock on the 8-state FSM, the per-facility `ClearanceTemplate`
vocabulary, and the multi-binding shape (typed CORA refs +
`ExternalRefBinding`).

## Why this scenario exists

**First scenario-tier exercise of the Safety BC.** The Safety BC
ships with the 8-state Clearance FSM (Defined ->
Submitted -> UnderReview -> Approved -> Active -> Expired |
Superseded, with Rejected as terminal-bad), 11 slices, and the
APS ESAF as one of 10 surveyed facility form-types. To date no
`test_2bm_*` scenario has registered a Clearance — the
`test_aps_facility.py` install seeds a placeholder umbrella ESAF
but never walks the FSM. This scenario is the source-of-truth
operator narrative for "proposal arrives -> Clearance issued ->
review chain -> Active".

The sibling scenario `test_2bm_run_start_gated_by_clearance.py`
exercises the cross-BC integration (Run.start gating on Clearance
status); this scenario stays inside the Safety BC so the FSM walk
is unambiguous.

This scenario exercises:

  - `register_clearance` with realistic ESAF shape: bound to the
    Subject (sample-level hazard) + an `ExternalRefBinding` to the
    proposal id (since CORA does not model Proposal aggregates;
    that binding wraps an `Identifier(scheme, value)` pair).
  - `submit_clearance` (Defined -> Submitted; PI signs off on the
    submitted form).
  - `start_clearance_review` (Submitted -> UnderReview;
    `first_reviewer_role="BeamlineScientist"`).
  - `append_clearance_review_step` x 2 capturing the 2-step
    review chain (BeamlineScientist + ESRB), both Approved.
  - `approve_clearance` (UnderReview -> Approved; permitted only
    when the most recent step ended in Approved).
  - `activate_clearance` (Approved -> Active; the gate-ready
    terminal-good state).

## Domain shape (operator narrative)

  1. Proposal 2026-1234 arrives. The 2-BM coordinator opens
     intake (PI + Subject + Campaign registered per the standard
     `_beamtime_fixture` ceremony).
  2. The Beamline Scientist registers the ESAF against the
     Subject sample + the proposal id (via ExternalRefBinding) +
     declares a hazard for the porous-sandstone sample (NFPA704
     low-rating).
  3. PI submits the ESAF for review.
  4. Beamline Scientist starts the review chain.
  5. Beamline Scientist reviews step 0 and approves.
  6. ESRB (Experiment Safety Review Board) reviews step 1 and
     approves.
  7. Coordinator approves the Clearance (UnderReview -> Approved).
  8. Coordinator activates the Clearance (Approved -> Active);
     the proposal is ready for its first Run.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The Clearance FSM
walk and the Run.start gate are separable concerns:

  - This scenario captures the operator narrative around the
    safety-form workflow itself (submit, review, approve,
    activate) without involving Run / Recipe BC at all.
  - The sibling `test_2bm_run_start_gated_by_clearance` scenario
    captures the cross-BC integration (Run.start fails without
    an Active Clearance; succeeds once one exists).

Bundling would conflate "the Safety FSM works" with "the Safety
gate fires from Run BC".

## What this scenario surfaces (gap-finding intent)

  - **ExternalRefBinding to Proposal is the canonical pattern.**
    CORA does not model Proposal as an aggregate (per
    `project_bc_map.md` line 111: Programs / Funding lines /
    Proposals "consumed via anti-corruption adapter, not modeled
    internally"). The ESAF binds to the proposal via
    `ExternalRefBinding(ref=Identifier(scheme="proposal", value="2026-1234"))`.
    If a facility ever needs CORA to model Proposal as an aggregate,
    this binding becomes a typed `ProposalBinding`. Watch item.
  - **Review chain length is per-facility convention.** This
    scenario uses 2 steps (BeamlineScientist + ESRB) matching
    APS practice; DESY DOOR has 3 steps; the FSM accepts any
    chain length. No CORA-side enforcement of chain length is
    expected.
  - **No projection assertion in this scenario.** The Safety BC
    projects to `proj_safety_clearance_summary` for the
    `PostgresClearanceLookup` adapter; the sibling
    `run_start_gated_by_clearance` scenario exercises that
    projection. This scenario stays at the aggregate level so the
    FSM walk is unambiguous.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.safety.aggregates.clearance import (
    ClearanceStatus,
    ExternalRefBinding,
    HazardDeclaration,
    SubjectBinding,
    load_clearance,
)
from cora.safety.aggregates.clearance.hazard_classification import NFPA704Rating
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
from cora.shared.identifier import Identifier
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import (
    BEAMLINE_SCIENTIST_ACTOR_ID,
    ESRB_ACTOR_ID,
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 18, 0, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000440bb")

# Root beamline Unit (facility-anchored via facility_code). Scenario tag:
# 440 (safety ops / proposal clearance FSM walk). The safety ops family
# takes 44x; future Safety scenarios (rejection path, expiration, amend /
# supersede) take 441..449.
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000440a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000440a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000440a31")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000440b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000440b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000440b21")

# Review-chain reviewers (`BEAMLINE_SCIENTIST_ACTOR_ID`, `ESRB_ACTOR_ID`)
# are registered by `install_aps_unit` (canonical fixture-owned UUIDs).
_CLEARANCE_ID = UUID("01900000-0000-7000-8000-000000440f01")

# Self-Facility slug seeded by `build_postgres_deps` default
# `InMemoryFacilityLookup` (matches `Settings.self_facility_code`).
_FACILITY_CODE = "cora"

# ESAF template within the self-Facility; lifespan-time auto-seed does
# not run for tests that build the kernel via `build_postgres_deps`
# directly, so the test pre-registers the template in the in-memory
# `ClearanceTemplateLookup` stub below (no projection write needed; the
# handler only consults the lookup port).
_TEMPLATE_CODE = "ESAF"
_TEMPLATE_ID: ClearanceTemplateId = ClearanceTemplateId(
    clearance_template_stream_id(_FACILITY_CODE, _TEMPLATE_CODE)
)

_DEVICES = (
    DeviceSpec(
        "Rotary",
        _ASSET_AEROTECH_ABRS_ID,
        "RotaryStage",
        _CAP_ROTARY_STAGE_ID,
    ),
    DeviceSpec("Camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
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


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        *beamtime_id_prefix(spec=_BEAMTIME),
        # register_clearance: clearance_id, event_id
        _CLEARANCE_ID,
        e(),
        # submit_clearance: event_id
        e(),
        # start_clearance_review: event_id
        e(),
        # append_clearance_review_step x 2: event_id each
        e(),
        e(),
        # approve_clearance: event_id
        e(),
        # activate_clearance: event_id
        e(),
    ]


@pytest.mark.integration
async def test_proposal_clearance_walks_to_active(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + beamtime intake, register ESAF Clearance
    bound to the Subject + proposal ExternalRefBinding, walk the full
    FSM (Defined -> Submitted -> UnderReview -> Approved -> Active)
    with a 2-step review chain (BeamlineScientist + ESRB). Assert
    each transition lands and Active is the terminal state."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # Pre-seed the in-memory ClearanceTemplateLookup so register_clearance's
    # cross-aggregate template lookup resolves to an Active ESAF template
    # at the self-Facility. The lifespan-time auto-seed (which writes
    # the projection that the Postgres adapter would read) does not run
    # under build_postgres_deps; this stub stands in for that projection.
    deps.clearance_template_lookup.register(  # type: ignore[attr-defined]
        template_id=_TEMPLATE_ID,
        facility_code=_FACILITY_CODE,
        code=_TEMPLATE_CODE,
        status="Active",
        version=1,
    )

    # ----- Facility hierarchy + beamtime intake -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    # ----- Safety BC: register ESAF for the proposal -----
    # Multi-bind: Subject (sample-level hazard claim) + ExternalRefBinding
    # for the proposal id (CORA does not model Proposal aggregate).
    # One HazardDeclaration: NFPA704 low-rating for the porous sandstone
    # sample (inert mineral, no special hazards).

    subject_binding = SubjectBinding(subject_id=_SUBJECT_ID)
    proposal_binding = ExternalRefBinding(
        ref=Identifier(scheme="proposal", value="2026-1234"),
    )

    new_clearance_id = await bind_register_clearance(deps)(
        RegisterClearance(
            template_id=_TEMPLATE_ID,
            facility_code=_FACILITY_CODE,
            title="Proposal 2026-1234 ESAF (porous sandstone tomography)",
            bindings=frozenset({subject_binding, proposal_binding}),
            declarations=frozenset(
                {
                    HazardDeclaration(
                        target=subject_binding,
                        classifications=frozenset(
                            {
                                NFPA704Rating(
                                    health=0,
                                    flammability=0,
                                    instability=0,
                                    special=None,
                                ),
                            }
                        ),
                        mitigations=frozenset({"PPE:safety_glasses"}),
                        notes=(
                            "Porous sandstone core sample; inert mineral; "
                            "no special hazards beyond standard PPE."
                        ),
                    ),
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_clearance_id == _CLEARANCE_ID

    defined = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert defined is not None
    assert defined.status == ClearanceStatus.DEFINED
    assert defined.template_id == _TEMPLATE_ID
    assert defined.facility_code.value == _FACILITY_CODE
    assert defined.review_steps == ()

    # ----- Defined -> Submitted (PI submits the form) -----

    await bind_submit_clearance(deps)(
        SubmitClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    submitted = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert submitted is not None
    assert submitted.status == ClearanceStatus.SUBMITTED

    # ----- Submitted -> UnderReview (BeamlineScientist starts review) -----

    await bind_start_review(deps)(
        StartClearanceReview(
            clearance_id=_CLEARANCE_ID,
            first_reviewer_role="BeamlineScientist",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    under_review = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert under_review is not None
    assert under_review.status == ClearanceStatus.UNDER_REVIEW

    # ----- Review step 0: BeamlineScientist approves -----

    await bind_append_review_step(deps)(
        AppendClearanceReviewStep(
            clearance_id=_CLEARANCE_ID,
            step_index=0,
            role="BeamlineScientist",
            actor_id=BEAMLINE_SCIENTIST_ACTOR_ID,
            decision="Approved",
            decided_at=_NOW,
            notes=(
                "Sample + plan reviewed; standard porous-media tomography; "
                "no novel hazards. Approved."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Review step 1: ESRB approves -----

    await bind_append_review_step(deps)(
        AppendClearanceReviewStep(
            clearance_id=_CLEARANCE_ID,
            step_index=1,
            role="ESRB",
            actor_id=ESRB_ACTOR_ID,
            decision="Approved",
            decided_at=_NOW,
            notes="Board concurrence; LGTM.",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    reviewed = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert reviewed is not None
    assert reviewed.status == ClearanceStatus.UNDER_REVIEW
    assert len(reviewed.review_steps) == 2
    assert reviewed.review_steps[0].role == "BeamlineScientist"
    assert reviewed.review_steps[0].decision == "Approved"
    assert reviewed.review_steps[1].role == "ESRB"
    assert reviewed.review_steps[1].decision == "Approved"

    # ----- UnderReview -> Approved -----

    await bind_approve_clearance(deps)(
        ApproveClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    approved = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert approved is not None
    assert approved.status == ClearanceStatus.APPROVED

    # ----- Approved -> Active (gate-ready) -----

    await bind_activate_clearance(deps)(
        ActivateClearance(clearance_id=_CLEARANCE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    active = await load_clearance(deps.event_store, _CLEARANCE_ID)
    assert active is not None
    assert active.status == ClearanceStatus.ACTIVE
    # Identity + bindings preserved across the full FSM walk.
    assert active.template_id == _TEMPLATE_ID
    assert active.facility_code.value == _FACILITY_CODE
    assert subject_binding in active.bindings
    assert proposal_binding in active.bindings

    # ----- Assert: Clearance stream carries the full FSM walk -----

    clearance_events, _version = await deps.event_store.load("Clearance", _CLEARANCE_ID)
    clearance_event_types = [e.event_type for e in clearance_events]
    # Register + Submit + StartReview + 2x AppendStep + Approve + Activate = 7
    assert clearance_event_types == [
        "ClearanceRegistered",
        "ClearanceSubmitted",
        "ClearanceReviewStarted",
        "ClearanceReviewStepAppended",
        "ClearanceReviewStepAppended",
        "ClearanceApproved",
        "ClearanceActivated",
    ]
