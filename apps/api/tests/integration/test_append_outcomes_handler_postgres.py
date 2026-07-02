"""End-to-end integration test: append_outcomes against real Postgres.

First concrete consumer of the entries_operation_procedure_outcomes table +
PostgresOutcomeStore. Stress-tests the JSON-array measurements storage shape +
lazy open-on-first-write + dedup-on-event_id + round-trip against actual
Postgres semantics. Mirrors test_append_diagnostics_handler_postgres.py.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    PostgresOutcomeStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.features.append_outcomes import (
    AppendProcedureOutcomes,
    OutcomeInput,
)
from cora.operation.features.append_outcomes import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="rotation-center steer",
        kind="characterization",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    started = ProcedureStarted(procedure_id=procedure_id, occurred_at=_NOW)
    for index, event in enumerate((registered, started)):
        new_event = to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=uuid4(),
            command_name="RegisterProcedure" if index == 0 else "StartProcedure",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        await deps_event_store.append(  # type: ignore[attr-defined]
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=index,
            events=[new_event],
        )


async def _read_outcomes(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
                event_id, procedure_id, logbook_id, iteration_index, point,
                measurements, succeeded, actuation_kind, sampled_at, occurred_at,
                recorded_at, correlation_id, causation_id
            FROM entries_operation_procedure_outcomes
            WHERE procedure_id = $1
            ORDER BY iteration_index, event_id
            """,
            procedure_id,
        )


def _entry(
    *, event_id: UUID, iteration_index: int, measurements: list[dict[str, Any]]
) -> OutcomeInput:
    return OutcomeInput(
        event_id=event_id,
        iteration_index=iteration_index,
        point={"energy": 8.0 + iteration_index},
        measurements=measurements,
        succeeded=True,
        actuation_kind="Physical",
        sampled_at=datetime(2026, 7, 1, 12, 0, iteration_index + 1, tzinfo=UTC),
    )


@pytest.mark.integration
async def test_append_outcomes_lazy_open_and_round_trip(db_pool: asyncpg.Pool) -> None:
    """Seed a Procedure, append two outcome rows; verify the lazy
    ProcedureOutcomeLogbookOpened landed and both rows persisted with their
    JSON measurements + iteration_index intact."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020e0b01")
    logbook_id = UUID("01900000-0000-7000-8000-0000020e0b02")
    open_event_id = UUID("01900000-0000-7000-8000-0000020e0b03")
    first_id = UUID("01900000-0000-7000-8000-0000020e0c01")
    second_id = UUID("01900000-0000-7000-8000-0000020e0c02")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    outcome_store = PostgresOutcomeStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, outcome_store=outcome_store)
    count = await handler(
        AppendProcedureOutcomes(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=first_id,
                    iteration_index=0,
                    measurements=[
                        {"name": "flux", "value": 12.5, "kind": "Scalar", "quality": "Good"}
                    ],
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 3
    assert events[2].event_type == "ProcedureOutcomeLogbookOpened"
    assert events[2].payload["kind"] == "outcome"
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.outcome_logbook_id == logbook_id

    rows = await _read_outcomes(db_pool, procedure_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["logbook_id"] == logbook_id
    assert row["iteration_index"] == 0
    assert row["succeeded"] is True
    assert row["actuation_kind"] == "Physical"
    assert row["recorded_at"] is not None
    import json

    measurements = row["measurements"]
    if isinstance(measurements, str):  # asyncpg returns jsonb as JSON string on plain SELECT
        measurements = json.loads(measurements)
    assert measurements[0]["name"] == "flux"
    assert measurements[0]["value"] == 12.5
    # The self-describing point round-trips through Postgres jsonb.
    point = row["point"]
    if isinstance(point, str):
        point = json.loads(point)
    assert point == {"energy": 8.0}

    # Second append skips the open, lands in the same logbook.
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    await bind_append(deps2, outcome_store=outcome_store)(
        AppendProcedureOutcomes(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=second_id,
                    iteration_index=1,
                    measurements=[
                        {"name": "flux", "value": 9.0, "kind": "Scalar", "quality": "Good"}
                    ],
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events2, version2 = await deps2.event_store.load("Procedure", procedure_id)
    assert version2 == 3
    open_count = sum(1 for e in events2 if e.event_type == "ProcedureOutcomeLogbookOpened")
    assert open_count == 1
    all_rows = await _read_outcomes(db_pool, procedure_id)
    assert len(all_rows) == 2
    assert {r["logbook_id"] for r in all_rows} == {logbook_id}


@pytest.mark.integration
async def test_append_outcomes_dedups_on_event_id_in_postgres(db_pool: asyncpg.Pool) -> None:
    """Producer retry with the same event_id is a silent no-op (first wins)."""
    procedure_id = UUID("01900000-0000-7000-8000-0000020e0d01")
    logbook_id = UUID("01900000-0000-7000-8000-0000020e0d02")
    open_event_id = UUID("01900000-0000-7000-8000-0000020e0d03")
    eid = UUID("01900000-0000-7000-8000-0000020e0d11")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    outcome_store = PostgresOutcomeStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, outcome_store=outcome_store)
    await handler(
        AppendProcedureOutcomes(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=eid,
                    iteration_index=0,
                    measurements=[{"name": "flux", "value": 1.0}],
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    await bind_append(deps2, outcome_store=outcome_store)(
        AppendProcedureOutcomes(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=eid,
                    iteration_index=1,
                    measurements=[{"name": "flux", "value": 9.0}],
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    rows = await _read_outcomes(db_pool, procedure_id)
    assert len(rows) == 1
    assert rows[0]["iteration_index"] == 0  # first wins
