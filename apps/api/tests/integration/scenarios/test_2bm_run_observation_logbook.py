"""Run observation logbook (baseline + monitor) at APS 2-BM.

cluster: Runs
archetype: routine
bc_primary: Run
bc_touches: Campaign, Equipment, Recipe, Run, Subject

Scenario test for the polymorphic per-Run observation logbook
exercising the SOSA-aligned `sampling_procedure` discriminator:
during a tomography Run the operator captures pre-scan baseline
observations (T_sample, ring current, motor positions) and then
periodic mid-scan monitor observations on the same channels. The
observations land in the Run's lazy-opened observation logbook (one
logbook per Run, lazy-opened on first write) with the entries
projected into the `entries_run_observations` Postgres table by the
handler-internal `ObservationStore`.

Phase operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_run_reading_design]] for the logbook
design lock (lazy open-on-first-write, polymorphic by
`sampling_procedure`, SOSA `sosa:samplingProcedure` alignment).
See [[project_logbook_entry_storage]] for Path B (per-Run,
high-volume, projection-backed entries) vs Path A / Path C
trichotomy.

## Why this scenario exists

**First scenario-tier exercise of `append_observations`** + the
lazy-open `RunObservationLogbookOpened` event + the polymorphic
`sampling_procedure` discriminator with BOTH `baseline` and
`monitor` values. The lower-tier integration test
`test_append_observations_handler_postgres.py` covers the
plumbing (entries land in the projection table; lazy open works;
PK dedup on retry) against a bypass-seeded `RunStarted` event.
This scenario is the operator-narrative source-of-truth for
"the observations logbook is how the Run captures continuous-channel
ephemera that don't belong in the Run aggregate's state but do
belong in its audit trail".

This scenario exercises:

  - `append_observations` first call: lazy emits
    `RunObservationLogbookOpened` on the Run stream + N entries land
    in `entries_run_observations`.
  - `append_observations` second call: skips the open emit + N
    more entries land.
  - Both `sampling_procedure="baseline"` (pre-scan one-shot) and
    `sampling_procedure="monitor"` (mid-scan periodic) values.
  - Cross-aggregate-friendly: the Run's own status remains
    `Running` throughout; observation appends are NOT a Run FSM
    transition (they live in a separate logbook).

## Domain shape (operator narrative)

  1. Beamtime intake + sample mounted + recipe ladder defined.
  2. Operator starts the tomography Run.
  3. Just before commanding the scan to begin, the operator
     captures pre-scan baseline observations (T_sample, ring
     current, motor_x) in one `append_observations` batch with
     `sampling_procedure="baseline"`. The Run's observation
     logbook is lazily opened on this first call
     (`RunObservationLogbookOpened` event emitted on the Run
     stream).
  4. ~600 projections in, the operator captures periodic
     monitor observations (same channels, fresh sampling) in a
     second `append_observations` batch with
     `sampling_procedure="monitor"`. The logbook is already
     open; no `RunObservationLogbookOpened` event is emitted.
  5. Run completes normally. The observation logbook stays
     attached to the Run forever (immutable event-sourced
     audit trail).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The observation
logbook is a separable concern from:

  - Run lifecycle transitions (start / hold / resume / complete
    / abort / stop / truncate).
  - Asset condition transitions (degrade / restore / fault).
  - Operator Decisions (RunDebriefer / EnergyChange).

It's how ephemeral per-Run continuous-channel data lands in the
audit trail; bundling with any of the above would conflate
"the Run's lifecycle" with "the Run's sensor capture".

## What this scenario surfaces (gap-finding intent)

  - **The polymorphic discriminator is a bare string.** Today
    `sampling_procedure` accepts any string; "baseline" and
    "monitor" are convention only. A future scenario or BC
    enhancement might promote to a closed `SamplingProcedure`
    enum if a third value emerges; the SOSA spec is itself
    open-set, so the bare-string approach is OK in principle.
  - **No projection over multiple Runs' observations.** A future
    "compare T_sample baselines across Runs on this Subject"
    query would benefit from a cross-Run projection over
    `entries_run_observations`; not built today.
  - **Reading entries are NOT in scope for the RunDebriefer
    agent.** Per [[project_run_debrief_design]] v1 read scope
    is Run+Observation+Verdict+Subject+Plan+Method+
    Practice+Cautions. Wait, `Observation` IS in the read scope
    -- but no current debrief scenario actually loads observations.
    Whether the agent's narrative would meaningfully change
    with observation-context is a watch item for a future
    debrief-with-observations scenario.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
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
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.run.aggregates.run import PostgresObservationStore
from cora.run.features.append_observations import (
    AppendObservations,
    ObservationInput,
)
from cora.run.features.append_observations import bind as bind_append_readings
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

_NOW = datetime(2026, 5, 18, 5, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000470bb")

# Scenario tag: 470 (run observations / baseline + monitor logbook).
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000470501")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000470a01")

_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_CAP_LINEAR_STAGE_ID = family_stream_id(FamilyName("LinearStage"))
_CAP_CAMERA_ID = family_stream_id(FamilyName("Camera"))
_CAP_SCINTILLATOR_ID = family_stream_id(FamilyName("Scintillator"))

_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000470a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000470a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000470a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000470a41")

_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000470b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000470b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000470b21")

_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000470d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0da26")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000470d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000470d21")

_RUN_ID = UUID("01900000-0000-7000-8000-000000470f02")
_READING_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000470f11")

# Per-entry event_ids for the two batches (pre-allocated for audit
# stability; producer-supplied per the at-least-once semantics).
_BASELINE_T_SAMPLE_ID = UUID("01900000-0000-7000-8000-00000047b001")
_BASELINE_RING_CURRENT_ID = UUID("01900000-0000-7000-8000-00000047b002")
_BASELINE_MOTOR_X_ID = UUID("01900000-0000-7000-8000-00000047b003")
_MONITOR_T_SAMPLE_ID = UUID("01900000-0000-7000-8000-000000470c81")
_MONITOR_RING_CURRENT_ID = UUID("01900000-0000-7000-8000-000000470c82")

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
    subject_name="porous sandstone core (Proposal 2026-1234, sample A, with observations)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime (with observations)",
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
        # add_run_to_campaign (2)
        e(),
        e(),
        # start_campaign
        e(),
        # First append_observations: lazy logbook_id + open event_id
        _READING_LOGBOOK_ID,
        e(),  # RunObservationLogbookOpened
        # Second append: no open event; just the row inserts (no
        # event-id from id queue because no Run event is appended)
        # complete_run
        e(),
        # close_campaign
        e(),
    ]


@pytest.mark.integration
async def test_run_observation_logbook_lazy_open_and_polymorphic_procedures(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed full chain, start Run, append baseline observations (lazy
    open), append monitor observations (skip open), complete Run.
    Assert: Run stream gets RunStarted + RunObservationLogbookOpened +
    RunCompleted (no second open event); 5 observation rows land with
    both sampling_procedure values across the two batches."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())
    observation_store = PostgresObservationStore(db_pool)

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
            reason="observation-logbook scenario setup",
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
            name="Proposal 2026-1234 sample A tomography (with observation logbook)",
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
    await bind_start_campaign(deps)(
        StartCampaign(campaign_id=_CAMPAIGN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Batch 1: pre-scan baseline observations (3 entries; lazy open) -----

    pre_scan_at = _NOW
    baseline_entries = (
        ObservationInput(
            event_id=_BASELINE_T_SAMPLE_ID,
            channel_name="T_sample",
            value=295.1,
            sampled_at=pre_scan_at,
            sampling_procedure="baseline",
            units="K",
        ),
        ObservationInput(
            event_id=_BASELINE_RING_CURRENT_ID,
            channel_name="S_SRCurrentAI",
            value=102.7,
            sampled_at=pre_scan_at,
            sampling_procedure="baseline",
            units="mA",
        ),
        ObservationInput(
            event_id=_BASELINE_MOTOR_X_ID,
            channel_name="SampleTop_X",
            value=12.345,
            sampled_at=pre_scan_at,
            sampling_procedure="baseline",
            units="mm",
        ),
    )
    baseline_count = await bind_append_readings(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=baseline_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert baseline_count == 3

    # ----- Batch 2: mid-scan monitor observations (2 entries; no open emit) -----

    mid_scan_at = _NOW + timedelta(minutes=10)
    monitor_entries = (
        ObservationInput(
            event_id=_MONITOR_T_SAMPLE_ID,
            channel_name="T_sample",
            value=295.4,
            sampled_at=mid_scan_at,
            sampling_procedure="monitor",
            units="K",
        ),
        ObservationInput(
            event_id=_MONITOR_RING_CURRENT_ID,
            channel_name="S_SRCurrentAI",
            value=101.9,
            sampled_at=mid_scan_at,
            sampling_procedure="monitor",
            units="mA",
        ),
    )
    monitor_count = await bind_append_readings(deps, observation_store=observation_store)(
        AppendObservations(run_id=_RUN_ID, entries=monitor_entries),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert monitor_count == 2

    # ----- Run completes normally -----

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

    # ----- Assert: Run stream carries the lazy-open event ONCE -----

    run_events, _ = await deps.event_store.load("Run", _RUN_ID)
    run_event_types = [e.event_type for e in run_events]
    # RunStarted + RunAddedToCampaign + RunObservationLogbookOpened (lazy)
    # + RunCompleted = 4. Second append must NOT emit a second
    # RunObservationLogbookOpened.
    assert run_event_types == [
        "RunStarted",
        "RunAddedToCampaign",
        "RunObservationLogbookOpened",
        "RunCompleted",
    ]
    assert run_event_types.count("RunObservationLogbookOpened") == 1

    # ----- Assert: 5 observation rows landed in entries_run_observations -----

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_id, channel_name, value, units, sampling_procedure
            FROM entries_run_observations
            WHERE run_id = $1
            ORDER BY sampled_at, channel_name
            """,
            _RUN_ID,
        )

    assert len(rows) == 5

    by_event_id = {r["event_id"]: r for r in rows}

    # Baseline rows: 3 entries with sampling_procedure="baseline"
    baseline_rows = [r for r in rows if r["sampling_procedure"] == "baseline"]
    assert len(baseline_rows) == 3

    # Monitor rows: 2 entries with sampling_procedure="monitor"
    monitor_rows = [r for r in rows if r["sampling_procedure"] == "monitor"]
    assert len(monitor_rows) == 2

    # Spot-check a baseline row's typed-column round trip
    t_sample_baseline = by_event_id[_BASELINE_T_SAMPLE_ID]
    assert t_sample_baseline["channel_name"] == "T_sample"
    assert t_sample_baseline["value"] == pytest.approx(295.1)
    assert t_sample_baseline["units"] == "K"

    # Spot-check a monitor row
    t_sample_monitor = by_event_id[_MONITOR_T_SAMPLE_ID]
    assert t_sample_monitor["channel_name"] == "T_sample"
    assert t_sample_monitor["value"] == pytest.approx(295.4)
    assert t_sample_monitor["sampling_procedure"] == "monitor"
