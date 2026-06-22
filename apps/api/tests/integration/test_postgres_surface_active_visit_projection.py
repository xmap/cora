"""End-to-end: `SurfaceActiveVisitProjection` against real Postgres.

Pins the load-bearing replay invariants the projection's SQL claims to
defend:
  - happy-path Take -> Released round-trip (since_at/released_at fill in
    correctly, partial UNIQUE leaves exactly one open row mid-flight)
  - Took(A) -> Released(A) -> Took(B) leaves only B open with A still
    visible in the history rows
  - replay-of-older-Took after a newer Took does NOT stomp the newer
    open row (the `since_at < $2` predicate on _TAKE_CONTROL_UPDATE_PRIOR)
  - cross-stream sibling race on the same Surface raises UniqueViolation
    on the second open INSERT (partial UNIQUE on (surface_id) WHERE
    released_at IS NULL)
  - Released event is idempotent under double-apply

Sibling: `test_postgres_caution_summary_projection.py`. Unit-tier
coverage of apply() dispatch lives in
`tests/unit/trust/visit/test_surface_active_visit_projection.py`; this
file pins the Postgres-side semantics that mocked-asyncpg cannot.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.trust._projections import register_trust_projections
from cora.trust.aggregates.visit import VisitType
from cora.trust.features import (
    record_visit_arrival,
    register_visit,
    release_control_of_surface,
    start_visit,
    take_control_of_surface,
)
from cora.trust.projections.surface_active_visit import SurfaceActiveVisitProjection
from tests.integration._helpers import build_postgres_deps

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_T0 = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=5)
_T2 = _T0 + timedelta(minutes=10)
_T3 = _T0 + timedelta(minutes=15)


def _deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _drain(pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_trust_projections(registry)
    await drain_projections(pool, registry, deadline_seconds=2.0)


async def _seed_in_progress_visit(
    pool: asyncpg.Pool, visit_id: UUID, surface_id: UUID, policy_id: UUID
) -> None:
    """Drive a fresh Visit through register/arrive/start so it is eligible
    for take_control_of_surface, and drain so the visit_summary FK row
    exists for the surface_active_visit projection's FK constraint."""
    await register_visit.bind(_deps(pool, [uuid4()], _T0))(
        register_visit.RegisterVisit(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            type=VisitType.USER,
            planned_start_at=_T0,
            planned_end_at=_T0 + timedelta(hours=8),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await record_visit_arrival.bind(_deps(pool, [uuid4()], _T0))(
        record_visit_arrival.RecordVisitArrival(visit_id=visit_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_visit.bind(_deps(pool, [uuid4()], _T0))(
        start_visit.StartVisit(visit_id=visit_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(pool)


def _took_stored(visit_id: UUID, surface_id: UUID, occurred_at: datetime) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Visit",
        stream_id=visit_id,
        version=1,
        event_type="VisitSurfaceControlTaken",
        schema_version=1,
        payload={
            "visit_id": str(visit_id),
            "surface_id": str(surface_id),
            "occurred_at": occurred_at.isoformat(),
        },
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
    )


def _released_stored(visit_id: UUID, surface_id: UUID, occurred_at: datetime) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Visit",
        stream_id=visit_id,
        version=1,
        event_type="VisitSurfaceControlReleased",
        schema_version=1,
        payload={
            "visit_id": str(visit_id),
            "surface_id": str(surface_id),
            "occurred_at": occurred_at.isoformat(),
        },
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
    )


@pytest.mark.integration
async def test_take_then_release_round_trip(db_pool: asyncpg.Pool) -> None:
    visit_id = uuid4()
    surface_id = uuid4()
    policy_id = uuid4()
    await _seed_in_progress_visit(db_pool, visit_id, surface_id, policy_id)
    await take_control_of_surface.bind(_deps(db_pool, [uuid4()], _T1))(
        take_control_of_surface.TakeControlOfSurface(visit_id=visit_id, surface_id=surface_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT visit_id, since_at, released_at FROM proj_trust_surface_active_visit "
            "WHERE surface_id = $1",
            surface_id,
        )
    assert row is not None
    assert row["visit_id"] == visit_id
    assert row["since_at"] == _T1
    assert row["released_at"] is None

    await release_control_of_surface.bind(_deps(db_pool, [uuid4()], _T2))(
        release_control_of_surface.ReleaseControlOfSurface(
            visit_id=visit_id, surface_id=surface_id
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT released_at FROM proj_trust_surface_active_visit WHERE surface_id = $1",
            surface_id,
        )
    assert row is not None
    assert row["released_at"] == _T2


@pytest.mark.integration
async def test_stale_replay_of_older_took_does_not_stomp_newer_open_row(
    db_pool: asyncpg.Pool,
) -> None:
    """Replay of an OLDER Took(A,t1) after a NEWER Took(B,t3) is committed
    must NOT close B's open row. The `since_at < $2` predicate is the
    guard; without it the stale Took's UPDATE would set B.released_at=t1."""
    visit_a = uuid4()
    visit_b = uuid4()
    surface_id = uuid4()
    policy_id = uuid4()
    await _seed_in_progress_visit(db_pool, visit_a, surface_id, policy_id)

    surface_b = uuid4()
    await _seed_in_progress_visit(db_pool, visit_b, surface_b, policy_id)

    projection = SurfaceActiveVisitProjection()
    async with db_pool.acquire() as conn:
        await projection.apply(_took_stored(visit_a, surface_id, _T1), conn)
        await projection.apply(_released_stored(visit_a, surface_id, _T2), conn)
        await projection.apply(_took_stored(visit_b, surface_id, _T3), conn)
        await projection.apply(_took_stored(visit_a, surface_id, _T1), conn)

    async with db_pool.acquire() as conn:
        b_row = await conn.fetchrow(
            "SELECT released_at FROM proj_trust_surface_active_visit "
            "WHERE surface_id = $1 AND visit_id = $2 AND since_at = $3",
            surface_id,
            visit_b,
            _T3,
        )
    assert b_row is not None
    assert b_row["released_at"] is None, (
        "replayed older Took(A) must not stomp newer open Took(B) row"
    )


@pytest.mark.integration
async def test_cross_stream_sibling_take_raises_unique_violation(
    db_pool: asyncpg.Pool,
) -> None:
    """The partial UNIQUE INDEX on (surface_id) WHERE released_at IS NULL
    is the load-bearing cross-stream guard. When two siblings race for
    the same Surface and the second's since_at is NOT strictly after the
    first's (the production-race shape: concurrent commits with
    same/near-same timestamps), stmt 1 fails to close the prior row and
    stmt 2 hits the partial UNIQUE.

    Decider rejects this at command time; this test pins the DB-layer
    last-line-of-defense per the migration comment block."""
    visit_a = uuid4()
    visit_b = uuid4()
    surface_id = uuid4()
    policy_id = uuid4()
    await _seed_in_progress_visit(db_pool, visit_a, surface_id, policy_id)
    surface_b = uuid4()
    await _seed_in_progress_visit(db_pool, visit_b, surface_b, policy_id)

    projection = SurfaceActiveVisitProjection()
    async with db_pool.acquire() as conn:
        await projection.apply(_took_stored(visit_a, surface_id, _T2), conn)

    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        async with db_pool.acquire() as conn:
            await projection.apply(_took_stored(visit_b, surface_id, _T1), conn)


@pytest.mark.integration
async def test_released_apply_is_idempotent_on_replay(db_pool: asyncpg.Pool) -> None:
    """Double-apply of the same Released event leaves the projection in
    the same state: released_at remains the first apply's timestamp,
    second apply is a no-op since the row's released_at is no longer NULL."""
    visit_id = uuid4()
    surface_id = uuid4()
    policy_id = uuid4()
    await _seed_in_progress_visit(db_pool, visit_id, surface_id, policy_id)

    projection = SurfaceActiveVisitProjection()
    released_event = _released_stored(visit_id, surface_id, _T2)
    async with db_pool.acquire() as conn:
        await projection.apply(_took_stored(visit_id, surface_id, _T1), conn)
        await projection.apply(released_event, conn)
        await projection.apply(released_event, conn)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT released_at FROM proj_trust_surface_active_visit "
            "WHERE surface_id = $1 AND visit_id = $2",
            surface_id,
            visit_id,
        )
    assert row is not None
    assert row["released_at"] == _T2
