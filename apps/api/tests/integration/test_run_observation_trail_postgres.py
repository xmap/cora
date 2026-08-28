"""Integration: PostgresRunObservationTrail against real Postgres.

Seeds rows through PostgresObservationStore (so recorded_at, occurred_at
and sampled_at are all real DB round-trips), then reads them back oldest
first through the trail. Mirrors `test_run_channel_lookup_postgres.py`'s
seeding pattern.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.run.adapters import PostgresRunObservationTrail
from cora.run.aggregates.run import Observation, PostgresObservationStore

_NOW = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def _obs(
    run_id: UUID,
    channel: str,
    *,
    value: float | None = None,
    categorical_value: str | None = None,
    sampling_procedure: str = "monitor",
    is_simulated: bool = False,
) -> Observation:
    return Observation(
        event_id=uuid4(),
        run_id=run_id,
        logbook_id=uuid4(),
        actor_id=uuid4(),
        command_name="AppendObservations",
        channel_name=channel,
        value=value,
        categorical_value=categorical_value,
        units="counts",
        sampling_procedure=sampling_procedure,
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
        is_simulated=is_simulated,
    )


@pytest.mark.integration
async def test_read_returns_empty_for_a_run_with_no_observations(db_pool: asyncpg.Pool) -> None:
    trail = PostgresRunObservationTrail(db_pool)
    rows = await trail.read_run_observations(run_id=uuid4(), limit=10)
    assert rows == []


@pytest.mark.integration
async def test_read_returns_rows_oldest_first_by_recorded_at(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    trail = PostgresRunObservationTrail(db_pool)

    first = _obs(run_id, "images", value=1.0)
    await store.append([first])
    await asyncio.sleep(0.01)
    second = _obs(run_id, "images", value=2.0)
    await store.append([second])

    rows = await trail.read_run_observations(run_id=run_id, limit=10)

    assert [r.event_id for r in rows] == [first.event_id, second.event_id]
    assert rows[0].recorded_at < rows[1].recorded_at


@pytest.mark.integration
async def test_read_round_trips_the_three_timestamps_as_timezone_aware(
    db_pool: asyncpg.Pool,
) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    trail = PostgresRunObservationTrail(db_pool)
    obs = _obs(run_id, "images", value=1.0)
    await store.append([obs])

    rows = await trail.read_run_observations(run_id=run_id, limit=10)

    assert len(rows) == 1
    row = rows[0]
    assert row.sampled_at.tzinfo is not None
    assert row.occurred_at.tzinfo is not None
    assert row.recorded_at.tzinfo is not None
    assert row.occurred_at == obs.occurred_at


@pytest.mark.integration
async def test_read_round_trips_both_value_and_categorical_shapes(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    trail = PostgresRunObservationTrail(db_pool)

    numeric = _obs(run_id, "images", value=42.0)
    categorical = _obs(run_id, "ScanType", categorical_value="Fly", sampling_procedure="baseline")
    await store.append([numeric, categorical])

    rows = await trail.read_run_observations(run_id=run_id, limit=10)

    by_channel = {r.channel_name: r for r in rows}
    assert by_channel["images"].value == 42.0
    assert by_channel["images"].categorical_value is None
    assert by_channel["ScanType"].categorical_value == "Fly"
    assert by_channel["ScanType"].value is None
    assert by_channel["ScanType"].sampling_procedure == "baseline"


@pytest.mark.integration
async def test_read_scopes_strictly_to_the_given_run(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    other_run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    trail = PostgresRunObservationTrail(db_pool)

    await store.append([_obs(run_id, "images", value=1.0)])
    await store.append([_obs(other_run_id, "images", value=2.0)])

    rows = await trail.read_run_observations(run_id=run_id, limit=10)

    assert len(rows) == 1
    assert rows[0].value == 1.0


@pytest.mark.integration
async def test_read_limit_truncates_to_the_oldest_prefix(db_pool: asyncpg.Pool) -> None:
    run_id = uuid4()
    store = PostgresObservationStore(db_pool)
    trail = PostgresRunObservationTrail(db_pool)

    seeded: list[Observation] = []
    for i in range(5):
        obs = _obs(run_id, "images", value=float(i))
        await store.append([obs])
        seeded.append(obs)
        await asyncio.sleep(0.01)

    rows = await trail.read_run_observations(run_id=run_id, limit=3)

    assert [r.event_id for r in rows] == [o.event_id for o in seeded[:3]]
