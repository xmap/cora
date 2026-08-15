"""Integration: CaptureProgressFeeder writes through the REAL
AppendObservations + FeedHeartbeatStore path against Postgres.

Mirrors test_sim_observation_feeder_postgres.py's shape (CORA's other
real feeder over the same write contract), adjusted for
CaptureProgressFeeder's own principal (CAPTURE_PROGRESS_FEEDER_AGENT_ID,
not the sim principal) and its `open_captures` lookup rather than a
fixed run_id.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_capture_progress_feeder import CAPTURE_PROGRESS_FEEDER_AGENT_ID
from cora.api._capture_progress_feeder import CaptureProgressFeeder
from cora.infrastructure.event_envelope import to_new_event
from cora.run.adapters import PostgresRunChannelLookup
from cora.run.aggregates.run import PostgresFeedHeartbeatStore, PostgresObservationStore
from cora.run.aggregates.run.events import RunStarted, event_type_name, to_payload
from cora.run.features.append_observations import bind as bind_append
from cora.run.ports.capture_observer import CaptureProgressObservation
from cora.shared.reach import ReachTier
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000cc")
_CODE = "2bmb-tomoscan"


async def _seed_run_started(event_store: object, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="capture-progress-feeder Run",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await event_store.append(  # type: ignore[attr-defined]
        stream_type="Run", stream_id=run_id, expected_version=0, events=[new_event]
    )


def _progress(
    role: str, value: float, *, commanded_total: float | None = None
) -> CaptureProgressObservation:
    return CaptureProgressObservation(
        capture_code=_CODE,
        role=role,
        value=value,
        commanded_total=commanded_total,
        reach_tier=ReachTier.RELAYED,
        observed_at=_NOW,
        source_kind="EpicsPv",
        source_id=f"2bmb:TomoScan:{role}",
    )


@pytest.mark.integration
async def test_feeder_writes_real_rows_under_its_own_principal(db_pool: asyncpg.Pool) -> None:
    run_id = UUID("01900000-0000-7000-8000-0000cf7d0a01")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    await _seed_run_started(deps.event_store, run_id)

    append = bind_append(deps, observation_store=PostgresObservationStore(db_pool))
    lookup = PostgresRunChannelLookup(db_pool)
    feeder = CaptureProgressFeeder(
        deps=deps,
        append_observations=append,
        feed_heartbeat_store=PostgresFeedHeartbeatStore(db_pool),
        open_captures=lambda: {_CODE: run_id},
        principal_id=CAPTURE_PROGRESS_FEEDER_AGENT_ID,
    )

    feeder.offer(_progress("images_saved", 100.0))
    feeder.offer(_progress("images_saved", 800.0))
    feeder.offer(_progress("images_collected", 802.0))
    await feeder.flush_capture(_CODE)

    saved = await lookup.read_run_channel_latest(run_id=run_id, channel_name="images_saved")
    collected = await lookup.read_run_channel_latest(run_id=run_id, channel_name="images_collected")
    assert saved is not None
    assert saved.value == 800.0  # latest-wins decimation
    assert collected is not None
    assert collected.value == 802.0

    # Principal split: every row this feeder writes is attributable to
    # its OWN Agent, distinguishable from RunWitness or a sim feeder at
    # the actor_id layer.
    async with db_pool.acquire() as conn:
        actor_ids = await conn.fetch(
            "SELECT DISTINCT actor_id FROM entries_run_observations WHERE run_id = $1", run_id
        )
    assert [r["actor_id"] for r in actor_ids] == [CAPTURE_PROGRESS_FEEDER_AGENT_ID]


@pytest.mark.integration
async def test_feeder_flush_writes_a_heartbeat_read_feed_health_sees(
    db_pool: asyncpg.Pool,
) -> None:
    run_id = UUID("01900000-0000-7000-8000-0000cf7d0b01")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    await _seed_run_started(deps.event_store, run_id)

    append = bind_append(deps, observation_store=PostgresObservationStore(db_pool))
    lookup = PostgresRunChannelLookup(db_pool)
    feeder = CaptureProgressFeeder(
        deps=deps,
        append_observations=append,
        feed_heartbeat_store=PostgresFeedHeartbeatStore(db_pool),
        open_captures=lambda: {_CODE: run_id},
        principal_id=CAPTURE_PROGRESS_FEEDER_AGENT_ID,
    )

    health_before = await lookup.read_feed_health(run_id=run_id)
    assert health_before.latest_heartbeat_recorded_at is None

    feeder.offer(_progress("images_saved", 1.0))
    await feeder.flush_capture(_CODE)

    health_after = await lookup.read_feed_health(run_id=run_id)
    assert health_after.latest_heartbeat_recorded_at is not None


@pytest.mark.integration
async def test_feeder_heartbeats_a_quiet_open_capture_against_real_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """The contract this slice's gate review fixed, proven against a
    real database: a capture with an open Run but NOTHING buffered
    still gets a heartbeat row."""
    run_id = UUID("01900000-0000-7000-8000-0000cf7d0c01")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    await _seed_run_started(deps.event_store, run_id)

    append = bind_append(deps, observation_store=PostgresObservationStore(db_pool))
    lookup = PostgresRunChannelLookup(db_pool)
    feeder = CaptureProgressFeeder(
        deps=deps,
        append_observations=append,
        feed_heartbeat_store=PostgresFeedHeartbeatStore(db_pool),
        open_captures=lambda: {_CODE: run_id},
        principal_id=CAPTURE_PROGRESS_FEEDER_AGENT_ID,
    )

    await feeder.flush_capture(_CODE)  # nothing ever offered

    health = await lookup.read_feed_health(run_id=run_id)
    assert health.latest_heartbeat_recorded_at is not None
    async with db_pool.acquire() as conn:
        observation_count = await conn.fetchval(
            "SELECT count(*) FROM entries_run_observations WHERE run_id = $1", run_id
        )
    assert observation_count == 0
