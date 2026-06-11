"""Retroactive Run.truncate after a control-room outage at APS 2-BM.

cluster: Runs
archetype: routine
bc_primary: Run
bc_touches: Campaign, Equipment, Recipe, Run, Subject

Scenario test for the de-facto-dead Run cleanup pathway: an
overnight tomography Run was in flight when the storage ring
beam dumped + the operator console crashed (no laptop power);
nobody held the Run, and the IOC machines were also down so
TomoScan stopped capturing. When the operator walks in the next
morning, the Run is technically still `Running` in CORA's
event store, but de facto dead. The operator records the
truncation with the operator's best-guess `interrupted_at`
timestamp.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. The `truncate_run` slice is the retroactive-cleanup
terminal distinct from stop (controlled-exit while system is
responsive) and abort (operator-decided emergency-exit).

## Why this scenario exists

**First scenario-tier exercise of `truncate_run` + the
`interrupted_at` field.** Sibling scenarios in this batch:

  - `test_2bm_run_hold_resume_cycle.py` covers hold/resume.
  - `test_2bm_run_stopped_early.py` covers stop_run.
  - THIS scenario covers `truncate_run` (Running -> Truncated).

This scenario exercises:

  - `truncate_run` from `Running` (the most common source state;
    a Held Run can also be truncated if the system was de-facto
    dead during the hold).
  - The `reason` field (required, 1-500 chars).
  - The optional `interrupted_at: datetime | None` — operator's
    best guess at when the actual interruption occurred (None
    when unknown). Distinct from the event's own `occurred_at`
    which is "when the operator filed the truncate".

## Domain shape (operator narrative)

  1. Beamtime intake + sample mounted + recipe ladder defined.
  2. Operator starts a long overnight tomography Run (1500
     projections at extended exposure).
  3. Sometime in the night, the storage ring beam dumps +
     control-room laptop loses power. Nobody hits hold;
     TomoScan stops capturing data when the IOC subnet drops
     out. CORA's event store still has the Run in `Running`
     state because no one called any slice.
  4. Operator walks in the next morning, sees the Run is
     "still running" but the IOC + beam have been dead for
     hours. Operator examines the control-room logs and
     estimates the interruption time as ~01:30 AM.
  5. Operator records the truncation via `truncate_run` with
     the reason citing "control-room outage; beam dumped
     overnight; system was de-facto dead since ~01:30 AM"
     and `interrupted_at=2026-05-18T01:30:00Z`. The Run
     transitions Running -> Truncated.
  6. No Dataset is registered (the partial data is unusable;
     the operator may keep the raw file for forensics but it
     does not become a CORA Dataset).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. Truncate vs
stop vs abort encode three distinct operator decisions:

  - Stop: "I'm intentionally exiting while the system is
    responsive; the data so far is valid."
  - Abort: "I'm emergency-exiting because something is wrong;
    the data so far should be reviewed before trust."
  - Truncate: "The system became de-facto dead without anyone
    noticing; I'm cleaning up CORA's bookkeeping to match
    reality."

Bundling would erase the operator-narrative distinction.

## What this scenario surfaces (gap-finding intent)

  - **CORA does not detect de-facto-dead Runs.** A separate
    liveness watchdog (heartbeat-monitor, projection-worker
    sweep, manual-only) is required to flag Runs that have
    been "Running" for unreasonable wall-clock durations. Per
    `truncate_run/command.py`: "the system itself does not
    detect de-facto-dead Runs (separate liveness concern);
    truncate is operator-driven". Watch item.
  - **`interrupted_at` is operator's best guess.** No
    cross-check against TomoScan IOC logs or beam-current
    history is performed. A future scenario could enrich
    truncate with a Decision aggregate carrying the actual
    evidence (beam-current trace, IOC log timestamps); not
    built today.
  - **No Dataset registered post-truncate.** The truncated
    Run produces no CORA Dataset; the partial raw file lives
    only in the filesystem. Whether a `Dataset(intent=Salvage)`
    or `Dataset(intent=Forensic)` value should be added for
    this case is deferred until the lineage demand emerges.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign import bind as bind_add_run_to_campaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.campaign.features.start_campaign import bind as bind_start_campaign
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.run.features.truncate_run import TruncateRun
from cora.run.features.truncate_run import bind as bind_truncate_run
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

# Morning-after wall clock when the operator walks in and files truncate.
_NOW = datetime(2026, 5, 18, 8, 0, 0, tzinfo=UTC)
# Operator's best guess at when the system actually went dead
# (overnight beam dump + console outage, ~6.5 hours earlier).
_INTERRUPTED_AT = _NOW - timedelta(hours=6, minutes=30)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000462bb")

# Scenario tag: 462 (run mid-lifecycle / truncated after outage).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000462501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000462a01")

_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000462c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000462c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000462c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000462c31")

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000462a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000462a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000462a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000462a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000462b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000462b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000462b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000462d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dcde")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000462d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000462d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000462f02")

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
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, overnight outage)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime (outage truncated)",
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
        # add_run_to_campaign (2 events)
        e(),
        e(),
        # start_campaign
        e(),
        # truncate_run (Running -> Truncated)
        e(),
    ]


@pytest.mark.integration
async def test_run_truncate_after_outage_lands_with_interrupted_at(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full imaging chain + activate + intake + mount + recipe,
    start Run, then (simulating an overnight outage) truncate the
    Run with an operator-best-guess `interrupted_at` timestamp.
    Assert Run reaches terminal Truncated with both the reason and
    the interrupted_at captured."""
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
            reason="overnight tomography scenario setup",
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
            name="Proposal 2026-1234 sample A overnight tomography",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 300,  # longer exposure for overnight scan
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            trigger_source="operator-manual; overnight unattended scan",
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

    # ----- Simulated overnight outage; morning operator files truncate -----
    # No CORA event was emitted during the outage (the system was de-
    # facto dead, no one called hold/stop/abort). The Run remains in
    # `Running` until the operator walks in and files this truncate.

    await bind_truncate_run(deps)(
        TruncateRun(
            run_id=_RUN_ID,
            reason=(
                "Control-room laptop lost power overnight; storage ring "
                "dumped beam around the same time; IOC subnet dropped "
                "out; system was de-facto dead since ~01:30 AM. No one "
                "could hold or stop the Run because nothing was alive "
                "to call CORA. Partial data is forensic-only; not "
                "registering a Dataset."
            ),
            interrupted_at=_INTERRUPTED_AT,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Run reached terminal Truncated -----

    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    assert run_event_types == [
        "RunStarted",
        "RunAddedToCampaign",
        "RunTruncated",
    ]

    # ----- Assert: RunTruncated carries reason + interrupted_at -----

    truncated_event = next(e for e in run_events if e.event_type == "RunTruncated")
    assert "lost power" in truncated_event.payload["reason"].lower()
    assert "de-facto dead" in truncated_event.payload["reason"]
    # interrupted_at is serialised as an ISO 8601 string in the event payload.
    assert truncated_event.payload["interrupted_at"] is not None
    assert "2026-05-18T01:30" in truncated_event.payload["interrupted_at"]
