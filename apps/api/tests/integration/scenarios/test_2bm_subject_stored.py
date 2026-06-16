"""Store a sample for re-measurement at APS 2-BM (terminal disposition).

cluster: Runs
archetype: setup
bc_primary: Subject
bc_touches: Access, Campaign, Subject

Closes out a Subject's custody by retaining it: the sample is kept at the
facility for a follow-up beamtime rather than returned or thrown away. This
is the `Removed -> Stored` terminal transition.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, the three terminal
dispositions (return / store / discard) are distinct sibling routines, each
with its own operator intent, so each gets its own scenario. This file
covers `Stored`.

## What this scenario surfaces

The disposition routine's only precondition is `Removed`, reached the short
way (register via beamtime open, then `remove_subject`); acquisition is not
replayed. `store_subject` carries no reason field: retaining a specimen
needs no audited justification, unlike `discard_subject`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.remove_subject import bind as bind_remove_subject
from cora.subject.features.store_subject import StoreSubject
from cora.subject.features.store_subject import bind as bind_store_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004c1cc1")

# Scenario tag: 4c1 (operations / subject stored).
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-0000004c1b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-0000004c1b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000004c1b21")

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Proposal 2026-1235 PI",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1235, sample B)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1235 beamtime",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # remove_subject (Received -> Removed)
        e(),  # store_subject (Removed -> Stored; the routine under test)
    ]


@pytest.mark.integration
async def test_store_subject_retains_the_specimen_at_the_facility(db_pool: asyncpg.Pool) -> None:
    """Register the sample, remove it from the experiment, then store it for a
    future beamtime. Assert the Subject stream is Registered -> Removed ->
    Stored and the terminal is reached in exactly three events."""
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

    await bind_store_subject(deps)(
        StoreSubject(subject_id=_SUBJECT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectRemoved",
        "SubjectStored",
    ]
