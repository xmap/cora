"""Mount sample at APS 2-BM.

cluster: Staging
archetype: setup
bc_primary: Subject
bc_touches: Access, Campaign, Equipment, Subject

Scenario test for the kinematic-mount routine: a Subject registered
during beamtime intake (in `Received` state) is mounted onto the
Aerotech rotary stage's kinematic tip, transitioning the Subject's
lifecycle to `Mounted`. Sourced from `2bm-docs manual/item_015.rst`
+ `pre_apsu/user/item_002.rst` (the canonical first-scan precondition).

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Step O-2 of the operations-phase canonical-acquisition chain
(O-1 = `beamtime_intake`, O-2 = `mount_sample`, O-3 =
`tomography_scan`). The mount routine is small but load-bearing:
no Run can execute against a Subject still in `Received` state, so
mount is the gate between intake and acquisition.

This scenario exercises the first Subject lifecycle TRANSITION:

  `Received` (intake genesis) `-> Mounted` (this scenario)

The cross-aggregate validation in the `mount_subject` decider
(target Asset must be in Active lifecycle) is exercised end-to-end.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, mount is a separable
operator routine: it has its own success/failure shape (good mount,
broken mount with backlash on remount, etc.), runs at a different
moment from intake (intake happens once per beamtime; mount happens
once per Subject change), and exercises a different aggregate (Subject
lifecycle vs Subject + Campaign genesis).

Intake setup is delegated to [`_beamtime_fixture.open_beamtime`](
_beamtime_fixture.py), the shared helper used by every operations-
phase scenario downstream of intake.

## Asset stack (just the Aerotech)

Mount needs the rotary stage Active (it's the apparatus the Subject
mounts onto). Other 2-BM Devices (linear stages, camera, scintillator,
shutter, focus motor) are not exercised by the mount routine itself;
they enter scope at scan time.

## What this scenario surfaces (gap-finding intent)

  - **Asset lifecycle gates Subject mount.** The decider rejects
    mount onto a Commissioned-but-not-Active Asset; only Active
    Assets accept Subjects. This is by design (per
    [[project_subject_mount_alignment_design]]), but the operator
    UX doesn't yet have a pre-flight check that explains *why* mount
    failed when the Asset is in the wrong state. Watch item: surface
    Asset-state in the mount failure error.
  - **Mount reason is operator tribal knowledge.** The `reason` field
    is free-text, 1-500 chars. Operators today might write "PI
    arrived; mounting sample A" or "remount after vibration test" or
    just "mount". Whether mount reason should be a closed-vocabulary
    `MountReason` enum is a watch item (would surface "first mount"
    vs "remount-after-X" distinctions for downstream queries).
  - **No Procedure is recorded for mount.** Mount is a single-event
    Subject state transition, not a multi-step Procedure. The
    operator's mount technique (alignment of the kinematic tip,
    torque on the screws) is implicit. Whether mount deserves a
    `mount_procedure` Procedure with step entries (Setpoint /
    Action / Check) is a watch item.
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

_NOW = datetime(2026, 5, 17, 8, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000402bb")

# Root beamline Unit (facility-anchored via facility_code). Scenario tag:
# 402 (operations / mount sample).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000402a01")

# Aerotech rotary (the mount apparatus): Family + Device
_CAP_ROTARY_STAGE_ID = family_stream_id(FamilyName("RotaryStage"))
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000402a11")

# Operations-phase intake aggregates (PI Actor + Subject + Campaign)
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000402b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000402b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000402b21")

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


_DEVICES = (DeviceSpec("Rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID),)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # activate_asset (Aerotech, required Active for mount): event_id
        e(),
        *beamtime_id_prefix(spec=_BEAMTIME),
        # mount_subject (the routine under test): event_id
        e(),
    ]


@pytest.mark.integration
async def test_mount_sample_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Open beamtime (Aerotech registered + activated, PI Actor + Subject
    + Campaign registered via `open_beamtime`), then mount the Subject
    onto the Aerotech's kinematic tip. Assert the Subject's lifecycle
    transitions Received -> Mounted with the correct asset_id + reason
    captured on the SubjectMounted event."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed facility + Aerotech rotary as the mount apparatus -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
    )

    # ----- Equipment BC: activate the Aerotech (required Active for mount) -----

    await bind_activate_asset(deps)(
        ActivateAsset(asset_id=_ASSET_AEROTECH_ABRS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Intake: PI Actor + Subject + Campaign via shared fixture -----

    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    # ----- Subject BC: mount the sandstone core onto the Aerotech rotary -----
    # Lifecycle: Received -> Mounted. The decider validates the Aerotech is
    # Active (it is, per the activate_asset call above) and emits
    # SubjectMounted(asset_id=Aerotech, reason=...).

    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=_SUBJECT_ID,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason=(
                "first mount for Proposal 2026-1234 beamtime; "
                "kinematic-tip alignment per PI's drawings"
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: Subject stream carries genesis + mount events -----

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 2
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",  # intake genesis (lands in Received)
        "SubjectMounted",  # this scenario (Received -> Mounted)
    ]
    mount_payload = subject_events[1].payload
    assert UUID(mount_payload["asset_id"]) == _ASSET_AEROTECH_ABRS_ID
    assert mount_payload["reason"] == (
        "first mount for Proposal 2026-1234 beamtime; kinematic-tip alignment per PI's drawings"
    )

    # ----- Assert: Aerotech stream landed activate + capability events -----

    aerotech_events, _ = await deps.event_store.load("Asset", _ASSET_AEROTECH_ABRS_ID)
    aerotech_event_types = [e.event_type for e in aerotech_events]
    assert aerotech_event_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetActivated",
    ]

    # ----- Assert: Campaign in Planned (no Run added yet) -----

    campaign_events, campaign_version = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    assert campaign_version == 1
    assert [e.event_type for e in campaign_events] == ["CampaignRegistered"]
