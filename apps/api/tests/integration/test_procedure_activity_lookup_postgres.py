"""Integration: PostgresProcedureActivityLookup against real Postgres.

Seeds rows through PostgresActivityStore (so recorded_at is the real DB
DEFAULT now()), then exercises the recency read. The max assertion keys
on the real DB-assigned recorded_at (read back from the table) so it is
deterministic, not clock-guessed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.operation.adapters.postgres_procedure_activity_lookup import (
    PostgresProcedureActivityLookup,
)
from cora.operation.aggregates.procedure.entries import Activity, PostgresActivityStore

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)


def _activity(procedure_id: UUID, logbook_id: UUID) -> Activity:
    return Activity(
        event_id=uuid4(),
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        actor_id=uuid4(),
        command_name="AppendProcedureActivities",
        step_kind="action",
        payload={"note": "step"},
        sampled_at=_NOW,
        occurred_at=_NOW,
        correlation_id=uuid4(),
        causation_id=None,
    )


async def _recorded_at(pool: asyncpg.Pool, event_id: UUID) -> datetime:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT recorded_at FROM entries_operation_procedure_activities WHERE event_id = $1",
            event_id,
        )


@pytest.mark.integration
async def test_recency_is_none_for_procedure_with_no_activity(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresProcedureActivityLookup(db_pool)
    recency = await lookup.read_procedure_activity_recency(procedure_id=uuid4())
    assert recency.latest_recorded_at is None


@pytest.mark.integration
async def test_recency_returns_max_recorded_at(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    store = PostgresActivityStore(db_pool)
    lookup = PostgresProcedureActivityLookup(db_pool)

    first = _activity(procedure_id, logbook_id)
    await store.append([first])
    await asyncio.sleep(0.01)  # guarantee a strictly later recorded_at
    second = _activity(procedure_id, logbook_id)
    await store.append([second])

    recency = await lookup.read_procedure_activity_recency(procedure_id=procedure_id)
    assert recency.latest_recorded_at == await _recorded_at(db_pool, second.event_id)


@pytest.mark.integration
async def test_recency_is_scoped_per_procedure(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    other = uuid4()
    store = PostgresActivityStore(db_pool)
    lookup = PostgresProcedureActivityLookup(db_pool)

    await store.append([_activity(procedure_id, uuid4())])

    recency = await lookup.read_procedure_activity_recency(procedure_id=other)
    assert recency.latest_recorded_at is None
