"""End-to-end PG integration test for rate_decision + ratings projection.

Pins the full write+read cycle under real Postgres:

  1. register_decision -> rate_decision -> drain projection.
  2. proj_decision_ratings row reflects latest-per-actor wins.
  3. confidence_at_rating denorm flows from proj_decision_summary.
  4. Re-rating the same Decision from the same actor UPDATEs (not
     inserts a duplicate row); audit-trail keeps both events on the
     stream.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import (
    event_type_name as actor_event_type_name,
)
from cora.access.aggregates.actor import (
    to_payload as actor_to_payload,
)
from cora.decision._projections import register_decision_projections
from cora.decision.aggregates.decision import (
    DecisionConfidenceSource,
    DecisionRating,
    load_decision,
)
from cora.decision.features import rate_decision, register_decision
from cora.decision.features.rate_decision import RateDecision
from cora.decision.features.register_decision import RegisterDecision
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.identity import ActorId
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_decision_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_actor(db_pool: asyncpg.Pool, actor_id: UUID) -> None:
    store = PostgresEventStore(db_pool)
    event = ActorRegistered(
        actor_id=actor_id,
        occurred_at=_NOW,
        kind=ActorKind.HUMAN,
    )
    new_event = to_new_event(
        event_type=actor_event_type_name(event),
        payload=actor_to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="RegisterActor",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Actor",
        stream_id=actor_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.integration
async def test_rate_decision_end_to_end_persists_and_projects(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(20)])

    actor_id = uuid4()
    await _seed_actor(db_pool, actor_id)

    decision_id = await register_decision.bind(deps)(
        RegisterDecision(
            decided_by=ActorId(actor_id),
            context="RunDebrief",
            choice="NominalCompletion",
            confidence=0.82,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    # Rate the Decision via the handler.
    await rate_decision.bind(deps)(
        RateDecision(
            decision_id=decision_id,
            rating=DecisionRating.USEFUL,
            comment="exactly what was needed",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    # Aggregate state has the rating.
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert _PRINCIPAL_ID in decision.ratings
    assert decision.ratings[_PRINCIPAL_ID].rating is DecisionRating.USEFUL
    assert decision.ratings[_PRINCIPAL_ID].comment == "exactly what was needed"

    # Projection has the row with confidence_at_rating denorm.
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT rating, comment, confidence_at_rating
              FROM proj_decision_ratings
             WHERE decision_id = $1 AND rated_by = $2
            """,
            decision_id,
            _PRINCIPAL_ID,
        )
    assert row is not None
    assert row["rating"] == "useful"
    assert row["comment"] == "exactly what was needed"
    assert row["confidence_at_rating"] == pytest.approx(0.82)


@pytest.mark.integration
async def test_rerating_same_decision_updates_projection_in_place(
    db_pool: asyncpg.Pool,
) -> None:
    """A second rating from the same actor UPDATEs the projection row
    (latest-per-actor wins) but appends a new event to the stream
    (audit trail keeps both)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(30)])

    actor_id = uuid4()
    await _seed_actor(db_pool, actor_id)

    decision_id = await register_decision.bind(deps)(
        RegisterDecision(
            decided_by=ActorId(actor_id),
            context="RunDebrief",
            choice="NominalCompletion",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    # First rating.
    await rate_decision.bind(deps)(
        RateDecision(
            decision_id=decision_id,
            rating=DecisionRating.MISLEADING,
            comment="initial review",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    # Second rating (changed mind) -- need a slightly later clock
    # for the latest-wins predicate.
    later = datetime(2026, 5, 17, 12, 5, 0, tzinfo=UTC)
    deps2 = build_postgres_deps(db_pool, now=later, ids=[uuid4() for _ in range(10)])
    await rate_decision.bind(deps2)(
        RateDecision(
            decision_id=decision_id,
            rating=DecisionRating.USEFUL,
            comment="on second look this was right",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    # Projection has exactly one row, with the latest rating AND
    # the original rated_by (gate-review test-coverage P1-2:
    # pin the composite-PK identity rather than implicitly trusting
    # the SELECT filter).
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT rating, comment, rated_by
              FROM proj_decision_ratings
             WHERE decision_id = $1
            """,
            decision_id,
        )
    assert len(rows) == 1
    assert rows[0]["rating"] == "useful"
    assert rows[0]["comment"] == "on second look this was right"
    assert rows[0]["rated_by"] == _PRINCIPAL_ID

    # Stream has both rating events (audit trail).
    events, version = await deps.event_store.load("Decision", decision_id)
    rating_events = [e for e in events if e.event_type == "DecisionRated"]
    assert len(rating_events) == 2
    assert [e.payload["rating"] for e in rating_events] == ["misleading", "useful"]
    assert version == 3  # genesis + 2 ratings
