"""Dismount sample at APS 2-BM.

cluster: Runs
archetype: setup
bc_primary: Subject
bc_touches: Equipment, Subject

Scenario test for the closing-the-loop routine: after a Subject has
been measured, the operator physically removes it from the Aerotech
kinematic tip, transitioning the Subject's lifecycle from `Measured`
back to `Received`. Sourced from `2bm-docs ops/item_018.rst`
(post-acquisition sample handling).

Step O-5 of the operations-phase canonical-acquisition chain.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Closes the Subject lifecycle loop. The full cycle is:

  `Received` (intake) `-> Mounted` (O-2) `-> Measured` (O-3) `-> Received` (this scenario)

A Subject in `Received` post-dismount is back in storage; it can
be re-mounted for follow-up acquisitions (still tracked under the
same proposal Campaign) or dispositioned (returned to PI, stored
indefinitely, or discarded — those terminal transitions are
separate slices not exercised here).

First scenario-tier exercise of:

  - `dismount_subject` slice (`Measured -> Received`)
  - `Subject.from_asset_id` cross-aggregate read at decider load
    time (the decider reads the mounted-on asset_id from prior
    state; it's not on the command)

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, dismount is a
separable operator routine. It runs after measurement, on its own
timeline (sample may sit on the tip for hours between scans, or
be dismounted immediately). Different success/failure shape
(graceful dismount, stuck-sample-requiring-tools dismount). Bundling
into the scan scenario would conflate acquisition with sample
handling.

## Asset stack (same as scan)

Full imaging chain registered + activated, sample mounted, scan
run. Dismount only touches the rotary (kinematic tip release), but
the full setup is replicated for narrative consistency.

## What this scenario surfaces (gap-finding intent)

  - **The dismounted Subject is back in `Received`, not in a
    distinct `Dismounted` state.** Per design, `Received` is the
    pre-mount AND post-dismount state. This is cleaner than
    introducing a fourth state, but reads ambiguously in logs
    ("was this Subject ever mounted?"). The Subject event history
    answers (a non-empty SubjectMounted/Dismounted pair confirms
    the cycle), but a derived projection field would be friendlier.
  - **Disposition is a separate concern.** After dismount, the
    Subject can be: returned to PI (`return_subject`), stored
    indefinitely (`store_subject`), or discarded
    (`discard_subject`). This scenario does not exercise any of
    those terminals; they belong on a sibling scenario (deferred
    until the disposition decision policy is locked).
  - **The `reason` field is operator tribal knowledge.** Same
    watch-item as `mount_subject.reason`: free-text 1-500 chars,
    no closed vocabulary. Operators today might write "scan
    complete; returning to storage" or "interrupted; remount
    later" or just "dismount".
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.subject.features.dismount_subject import DismountSubject
from cora.subject.features.dismount_subject import bind as bind_dismount_subject
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
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000405bb")

# Facility hierarchy. Scenario tag: 405 (operations / dismount sample).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000405a01")

# Aerotech (the mount apparatus)
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000405a11")

# Beamtime
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000405b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000405b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000405b21")


_DEVICES = (
    DeviceSpec(
        "Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID
    ),
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
        e(),  # activate_asset (Aerotech)
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        e(),  # measure_subject (synthetic; in real life triggered by Run completion)
        e(),  # dismount_subject (the routine under test)
    ]


@pytest.mark.integration
async def test_dismount_sample_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Replicate beamtime + mount + measure setup (the precondition
    states for a dismount), then exercise the dismount routine. Assert
    Subject lifecycle returns Measured -> Received and the dismount
    event captures the from_asset_id (read from prior state) + reason."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Facility + Aerotech -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )

    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=_ASSET_AEROTECH_ABRS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Beamtime + mount + (synthetic) measure -----

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
            reason="proposal scan setup; sample A on kinematic tip",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Skip the full scan ceremony (covered by O-3); just advance the Subject
    # to Measured directly. The dismount slice's precondition is status
    # in {Mounted, Measured}; we test the Measured -> Received path here.
    await bind_measure_subject(deps)(
        MeasureSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Subject BC: dismount (Measured -> Received) -----

    await bind_dismount_subject(deps)(
        DismountSubject(
            subject_id=_SUBJECT_ID,
            reason="scan complete; returning sample to PI storage container",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Subject stream carries the full cycle -----

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 4
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectMounted",
        "SubjectMeasured",
        "SubjectDismounted",
    ]

    # ----- Assert: dismount event captured from_asset_id (read from state) + reason -----

    dismount_payload = subject_events[3].payload
    assert UUID(dismount_payload["from_asset_id"]) == _ASSET_AEROTECH_ABRS_ID
    assert dismount_payload["reason"] == ("scan complete; returning sample to PI storage container")
