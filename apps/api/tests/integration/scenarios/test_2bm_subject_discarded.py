"""Discard a sample-of-opportunity at APS 2-BM (terminal disposition).

cluster: Runs
archetype: setup
bc_primary: Subject
bc_touches: Access, Campaign, Subject

Closes out a Subject's custody by disposal: a leftover sample-of-opportunity
with no owner is thrown away after measurement. This is the
`Removed -> Discarded` terminal transition, the one disposition that carries
a required `reason` (sample-handling + GDPR audit trail).

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, the three terminal
dispositions (return / store / discard) are distinct sibling routines, so
each gets its own scenario. This file covers `Discarded`, the only one with
an audited reason.

## What this scenario surfaces

The disposition routine's only precondition is `Removed`, reached the short
way (register via beamtime open, then `remove_subject`); acquisition is not
replayed. Unlike return / store, `discard_subject` requires a `reason`
(1-500 chars after trimming) so the audit record carries why the specimen
was destroyed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.subject.features.discard_subject import DiscardSubject
from cora.subject.features.discard_subject import bind as bind_discard_subject
from cora.subject.features.remove_subject import RemoveSubject
from cora.subject.features.remove_subject import bind as bind_remove_subject
from tests.integration._helpers import build_postgres_deps, make_pg_profile_store
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000004c2cc1")

# Scenario tag: 4c2 (operations / subject discarded).
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-0000004c2b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-0000004c2b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000004c2b21")

_DISCARD_REASON = "leftover sample-of-opportunity; no owner; discarded per sample-handling policy"

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="2-BM local contact",
    subject_id=_SUBJECT_ID,
    subject_name="leftover sandstone core (sample-of-opportunity)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="2-BM sample-of-opportunity handling",
    campaign_intent=CampaignIntent.COORDINATION,
    campaign_tags=frozenset({"sample_of_opportunity", "porous_media"}),
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # remove_subject (Received -> Removed)
        e(),  # discard_subject (Removed -> Discarded; the routine under test)
    ]


@pytest.mark.integration
async def test_discard_subject_records_the_audited_reason(db_pool: asyncpg.Pool) -> None:
    """Register the sample, remove it, then discard it with a reason. Assert
    the Subject stream is Registered -> Removed -> Discarded and the terminal
    event carries the trimmed operator reason."""
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

    await bind_discard_subject(deps)(
        DiscardSubject(subject_id=_SUBJECT_ID, reason=_DISCARD_REASON),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    subject_events, subject_version = await deps.event_store.load("Subject", _SUBJECT_ID)
    assert subject_version == 3
    assert [e.event_type for e in subject_events] == [
        "SubjectRegistered",
        "SubjectRemoved",
        "SubjectDiscarded",
    ]
    assert subject_events[2].payload["reason"] == _DISCARD_REASON
