"""Return a sample to the PI at APS 2-BM (terminal disposition).

cluster: Runs
archetype: setup
bc_primary: Subject
bc_touches: Access, Campaign, Subject

Closes out a Subject's custody: after the proposal's data is in hand, the
operator removes the sample from the experiment and returns the physical
specimen to the principal investigator. This is the `Removed -> Returned`
terminal transition.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, terminal disposition is its
own operator routine, separable from dismount (the kinematic tip release,
`Measured -> Received`). Return / store / discard are three distinct sibling
routines with distinct operator intent, so each gets its own scenario (the
`run_debriefer` trio precedent). This file covers `Returned`.

## What this scenario surfaces

The disposition routine's only precondition is `Removed`, so the scenario
reaches it the short way: register the sample (via the beamtime open), then
`remove_subject`. Mount + measure are not replayed; they belong to the
acquisition scenarios and are irrelevant to the terminal transition under
test. `return_subject` carries no reason field (unlike `discard_subject`):
returning a specimen to its owner needs no audited justification.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.remove_subject import bind as bind_remove_subject
from cora.subject.features.return_subject import ReturnSubject
from cora.subject.features.return_subject import bind as bind_return_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004c0cc1")

# Scenario tag: 4c0 (operations / subject returned).
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-0000004c0b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-0000004c0b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000004c0b21")

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
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # remove_subject (Received -> Removed)
        e(),  # return_subject (Removed -> Returned; the routine under test)
    ]


@pytest.mark.integration
async def test_return_subject_closes_custody_to_the_pi(db_pool: asyncpg.Pool) -> None:
    """Register the sample, remove it from the experiment, then return it to
    the PI. Assert the Subject stream is Registered -> Removed -> Returned and
    the terminal is reached in exactly three events."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    await open_beamtime(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    await bind_remove_subject(deps)(
        RemoveSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_return_subject(deps)(
        ReturnSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectRemoved",
        "SubjectReturned",
    ]
