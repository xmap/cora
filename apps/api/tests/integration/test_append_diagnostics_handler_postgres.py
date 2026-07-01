"""End-to-end integration test: append_diagnostics against real Postgres.

First concrete consumer of the entries_operation_procedure_diagnostics table +
PostgresDiagnosticStore. Stress-tests the JSON-payload storage shape + lazy
open-on-first-write + dedup-on-event_id + three-timestamp round-trip against
actual Postgres semantics. Mirrors test_append_activities_handler_postgres.py.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    PostgresDiagnosticStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.features.append_diagnostics import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)
from cora.operation.features.append_diagnostics import bind as bind_append
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


async def _read_diagnostics(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
                event_id, procedure_id, logbook_id, iteration_index, model_ref,
                payload, sampled_at, occurred_at, recorded_at,
                correlation_id, causation_id
            FROM entries_operation_procedure_diagnostics
            WHERE procedure_id = $1
            ORDER BY iteration_index, event_id
            """,
            procedure_id,
        )


def _entry(*, event_id: UUID, iteration_index: int, payload: dict[str, object]) -> DiagnosticInput:
    return DiagnosticInput(
        event_id=event_id,
        iteration_index=iteration_index,
        model_ref="botorch",
        payload=payload,
        sampled_at=datetime(2026, 7, 1, 12, 0, iteration_index + 1, tzinfo=UTC),
    )


@pytest.mark.integration
async def test_append_diagnostics_lazy_open_and_round_trip(db_pool: asyncpg.Pool) -> None:
    """Seed a Procedure, append two diagnostic rows; verify the lazy
    ProcedureDiagnosticLogbookOpened landed and both rows persisted with their
    JSON payloads + iteration_index + model_ref intact."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010d0b01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010d0b02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010d0b03")
    first_id = UUID("01900000-0000-7000-8000-0000010d0c01")
    second_id = UUID("01900000-0000-7000-8000-0000010d0c02")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    diagnostic_store = PostgresDiagnosticStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, diagnostic_store=diagnostic_store)
    count = await handler(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=first_id,
                    iteration_index=1,
                    payload={"lengthscale_offset": 0.8, "noise": 0.005, "acquisition_value": 0.12},
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 1

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 3
    assert events[2].event_type == "ProcedureDiagnosticLogbookOpened"
    open_payload = events[2].payload
    assert open_payload["kind"] == "diagnostic"
    assert open_payload["logbook_id"] == str(logbook_id)
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.diagnostic_logbook_id == logbook_id

    rows = await _read_diagnostics(db_pool, procedure_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["logbook_id"] == logbook_id
    assert row["iteration_index"] == 1
    assert row["model_ref"] == "botorch"
    assert row["occurred_at"] == _NOW
    # recorded_at is the DB's DEFAULT now() (real wall clock); occurred_at is the
    # test's fixed fake clock, so only assert the row was DB-stamped, not ordering.
    assert row["recorded_at"] is not None
    payload = row["payload"]
    if isinstance(payload, str):  # asyncpg returns jsonb as a JSON string on plain SELECT
        import json

        payload = json.loads(payload)
    assert payload == {"lengthscale_offset": 0.8, "noise": 0.005, "acquisition_value": 0.12}

    # Second append skips the open, lands in the same logbook.
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    await bind_append(deps2, diagnostic_store=diagnostic_store)(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=second_id,
                    iteration_index=2,
                    payload={"lengthscale_offset": 0.7, "noise": 0.004, "acquisition_value": 0.03},
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events2, version2 = await deps2.event_store.load("Procedure", procedure_id)
    assert version2 == 3
    open_count = sum(1 for e in events2 if e.event_type == "ProcedureDiagnosticLogbookOpened")
    assert open_count == 1
    all_rows = await _read_diagnostics(db_pool, procedure_id)
    assert len(all_rows) == 2
    assert {r["logbook_id"] for r in all_rows} == {logbook_id}


@pytest.mark.integration
async def test_append_diagnostics_dedups_on_event_id_in_postgres(db_pool: asyncpg.Pool) -> None:
    """Producer retry with the same event_id is a silent no-op (first wins)."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010d0d01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010d0d02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010d0d03")
    eid = UUID("01900000-0000-7000-8000-0000010d0d11")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    diagnostic_store = PostgresDiagnosticStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, diagnostic_store=diagnostic_store)
    await handler(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(_entry(event_id=eid, iteration_index=1, payload={"acquisition_value": 1.0}),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    await bind_append(deps2, diagnostic_store=diagnostic_store)(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(_entry(event_id=eid, iteration_index=2, payload={"acquisition_value": 9.0}),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    rows = await _read_diagnostics(db_pool, procedure_id)
    assert len(rows) == 1
    assert rows[0]["iteration_index"] == 1  # first wins


@pytest.mark.integration
async def test_diagnostics_payload_stores_as_real_jsonb(db_pool: asyncpg.Pool) -> None:
    """Payload persists as a real jsonb OBJECT so server-side `->>'key'` works."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010d0e01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010d0e02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010d0e03")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    diagnostic_store = PostgresDiagnosticStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    await bind_append(deps, diagnostic_store=diagnostic_store)(
        AppendProcedureDiagnostics(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=UUID("01900000-0000-7000-8000-0000010d0e11"),
                    iteration_index=1,
                    payload={"acquisition_value": 0.42},
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT payload->>'acquisition_value' AS acq
            FROM entries_operation_procedure_diagnostics
            WHERE procedure_id = $1
            """,
            procedure_id,
        )
    assert [r["acq"] for r in rows] == ["0.42"]
