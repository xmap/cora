"""Beamtime intake at APS 2-BM.

cluster: Staging
archetype: setup
bc_primary: Subject
bc_touches: Access, Campaign, Subject

Scenario test for the canonical first step of a proposal-driven
beamtime: the operator runs `dmagic` to pull the proposal metadata
from APS scheduling, then registers the PI as a CORA Actor, the
incoming sample as a CORA Subject, and opens a proposal-scoped
Campaign with the PI as lead. Sourced from `2bm-docs ops/item_018.rst`
+ `2bmb-bin/dmagic.sh`.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

This is CORA's first **operations-phase** scenario and the first
exercise of the Subject + Campaign BCs together. It opens the
operator's narrative for a proposal-driven beamtime:

  1. Operator pulls proposal metadata (`dmagic show && dmagic tag`).
  2. PI is registered as a CORA Actor (separate from the operator
     who is doing the registration).
  3. The sample arriving with the proposal is registered as a
     Subject (lands in `Received` state per Subject BC genesis).
  4. A Campaign is opened with PI as `lead_actor_id`, intent
     `Coordination`, tagged `proposal` + technique (`tomography`).
  5. Future scenarios (mount, scan, debrief, publish) consume this
     beamtime context via reuse fixtures.

No Run is executed here. The beamtime is OPEN; subsequent
operations-phase scenarios produce Runs under this Campaign.

## Why a separate scenario (not bundled into `first_proposal_scan`)

Per [scenarios/README.md](../README.md) Rule 1, one scenario = one
routine. The canonical first user acquisition is the SUM of intake
+ mount + scan + (optional) dismount + publish, which would be a
4-routine compendium. Each routine is separable and exercises
distinct aggregates, so each gets its own scenario file.

This scenario is the smallest of the chain: just Actor + Subject +
Campaign registration, no Run, no Procedure.

## Asset stack (none)

Beamtime intake doesn't touch motors, detectors, or optics. The
facility hierarchy (Argonne + APS + 2-BM Unit) IS registered via
`install_aps_unit` for narrative consistency with sibling scenarios
(the Campaign's lead Actor needs a registered Site to act under),
but no Devices are registered.

## What this scenario surfaces (gap-finding intent)

  - **PI Actor is OPERATOR-registered, not self-registered.** The
    PI is a guest scientist who never logs into CORA directly during
    intake; the operator (who has CORA credentials) registers the
    PI on their behalf. Per Campaign command-shape lock,
    `lead_actor_id` stays on the command (intentionally different
    from Caution's envelope-derived `authored_by`) so the
    operator can assign a PI lead distinct from themselves.
  - **`dmagic` external integration is out-of-scope today.** The
    real beamtime intake fetches proposal metadata from APS
    scheduling via `dmagic show`. This scenario records the PI
    name + Subject name + Campaign name as if they were
    operator-supplied; integrating `dmagic` as an external port
    (mirroring the LogbookMirror pattern) is a watch item.
  - **Subject genesis is in `Received` state.** Subject's lifecycle
    is `Received -> Mounted -> Measured -> Received` (per
    [[project_subject_mount_alignment_design]]); intake registers
    in Received, mount scenario transitions to Mounted.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.register_campaign import bind as bind_register_campaign
from cora.subject.features.register_subject import RegisterSubject
from cora.subject.features.register_subject import bind as bind_register_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._facility_fixture import (
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 17, 8, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000401bb")

# Facility hierarchy. Scenario tag: 401 (operations / beamtime intake).
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000401a01")

# Operations-phase aggregates registered by intake
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000401b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000401b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000401b21")


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    Intake registers no Devices, so `facility_id_prefix(devices=())`
    consumes only the 8 ids for actor + Argonne + APS + Unit
    (no Family defines, no Device registers).
    """
    e = uuid4
    return [
        *facility_id_prefix(
            unit_id=_2BM_UNIT_ID,
            devices=(),
        ),
        # register_actor (PI, separate from operator): actor_id, event_id
        _PI_ACTOR_ID,
        e(),
        # register_subject (sample arriving with the proposal): subject_id, event_id
        _SUBJECT_ID,
        e(),
        # register_campaign (proposal-scoped, PI as lead): campaign_id, event_id
        _CAMPAIGN_ID,
        e(),
    ]


@pytest.mark.integration
async def test_beamtime_intake_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility hierarchy, register the PI Actor (operator
    acting on PI's behalf), register the incoming Subject (lands in
    Received), open a proposal-scoped Coordination Campaign with the
    PI as lead. Assert the auditable record carries the full intake
    arc and the cross-aggregate references (Campaign.lead_actor_id ->
    PI, Campaign.subject_id -> Subject) resolve correctly."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed facility hierarchy: actor (operator) + Argonne -> APS -> 2-BM -----
    # No Devices: intake is pre-acquisition.

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        unit_id=_2BM_UNIT_ID,
        devices=(),
        unit_name="2-BM",
    )

    # ----- Access BC: register the PI as a separate Actor -----
    # Operator (principal) acts on PI's behalf during intake; PI is a guest
    # scientist who never logs into CORA directly. PI Actor is the
    # operator-assigned Campaign lead.

    await bind_register_actor(deps, profile_store=make_pg_profile_store(db_pool))(
        RegisterActor(name="Proposal 2026-1234 PI"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Subject BC: register the sample arriving with the proposal -----
    # Subject lands in Received state per Subject BC genesis. Mount scenario
    # transitions Received -> Mounted.

    await bind_register_subject(deps)(
        RegisterSubject(name="porous sandstone core (Proposal 2026-1234, sample A)"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Campaign BC: open a proposal-scoped Campaign with PI as lead -----
    # intent=Coordination (proposal-scoped acquisitions across multiple Runs);
    # subject_id pins this Campaign to the registered Subject (LOOSE policy
    # allows None or other Subjects in later Runs); tags carry the proposal
    # tag + technique vocabulary (tomography).

    await bind_register_campaign(deps)(
        RegisterCampaign(
            name="Proposal 2026-1234 beamtime",
            intent=CampaignIntent.COORDINATION,
            lead_actor_id=_PI_ACTOR_ID,
            subject_id=_SUBJECT_ID,
            description=(
                "Two-day beamtime for porous-sandstone CT under varying "
                "saturation conditions. PI brought 6 sample cores; sample A "
                "is the first to be mounted and imaged."
            ),
            tags=frozenset({"proposal", "tomography", "porous_media"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: facility hierarchy + 2 Actors + Subject + Campaign landed -----

    # Operator Actor (registered by install_aps_unit, principal_id == actor_id)
    operator_events, operator_version = await deps.event_store.load("Actor", _PRINCIPAL_ID)
    assert operator_version == 1
    assert [e.event_type for e in operator_events] == ["ActorRegisteredV2"]

    # PI Actor (registered separately by this scenario)
    pi_events, pi_version = await deps.event_store.load("Actor", _PI_ACTOR_ID)
    assert pi_version == 1
    assert [e.event_type for e in pi_events] == ["ActorRegisteredV2"]

    # Subject (lands in Received state)
    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 1
    assert [e.event_type for e in subject_events] == ["SubjectRegistered"]
    assert (
        subject_events[0].payload["name"] == "porous sandstone core (Proposal 2026-1234, sample A)"
    )

    # Campaign (Planned state per Campaign BC genesis; lead_actor_id resolves
    # to the PI Actor, subject_id resolves to the registered Subject)
    campaign_events, campaign_version = await deps.event_store.load("Campaign", _CAMPAIGN_ID)
    assert campaign_version == 1
    assert [e.event_type for e in campaign_events] == ["CampaignRegistered"]
    campaign_payload = campaign_events[0].payload
    assert campaign_payload["name"] == "Proposal 2026-1234 beamtime"
    assert campaign_payload["intent"] == "Coordination"
    assert UUID(campaign_payload["lead_actor_id"]) == _PI_ACTOR_ID
    assert UUID(campaign_payload["subject_id"]) == _SUBJECT_ID
    assert "proposal" in campaign_payload["tags"]
    assert "tomography" in campaign_payload["tags"]
    assert "porous_media" in campaign_payload["tags"]

    # ----- Assert: root Unit Asset landed (no Devices) -----

    _events, version = await deps.event_store.load("Asset", _2BM_UNIT_ID)
    assert version >= 1, f"Asset {_2BM_UNIT_ID} did not land"
