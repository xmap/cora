"""Acceptance test for Step 2 of the record exporter build brief.

Per `project_record_export_build_brief.md` step 2: a Procedure stream
folds to `Running` with its activity rows beside it, unfolded; an
unknown `stream_type` refuses rather than skips; zero rows exported is
an error.

The Procedure is built the same way
`test_append_activities_handler_postgres.py` does it: `ProcedureRegistered`
+ `ProcedureStarted` seeded directly into the event store (bypassing
`register_procedure`/`start_procedure`'s cross-aggregate validation,
which is not this test's concern), then the real `append_activities`
handler so `ProcedureActivitiesLogbookOpened` fires for real and rows
land in `entries_operation_procedure_activities`.

The "folds to Running" assertion reconstructs `StoredEvent`s from
`export_record`'s own rendered `streams` output (not from a fresh
`event_store.load`), because the point of the acceptance test is that
the EXPORTED representation is complete and correct enough to fold, the
same property the standalone verifier (step 5) will depend on.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC as _UTC
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.record_export import (
    EmptyExportError,
    UnknownStreamTypeError,
    export_record,
)
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    ProcedureStarted,
    ProcedureStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=_UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(event_store: object, procedure_id: UUID) -> None:
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="Vessel-A bakeout",
        kind="bakeout",
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
        await event_store.append(  # type: ignore[attr-defined]
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=index,
            events=[new_event],
        )


def _stored_event_from_rendered_row(row: dict[str, object]) -> StoredEvent:
    """Reconstruct a `StoredEvent` from one of `export_record`'s rendered
    `streams` rows, undoing F6 rendering. This is exactly the
    reconstruction the standalone verifier (step 5) will need to do."""
    return StoredEvent(
        position=row["position"],  # type: ignore[arg-type]
        event_id=UUID(row["event_id"]),  # type: ignore[arg-type]
        stream_type=row["stream_type"],  # type: ignore[arg-type]
        stream_id=UUID(row["stream_id"]),  # type: ignore[arg-type]
        version=row["version"],  # type: ignore[arg-type]
        event_type=row["event_type"],  # type: ignore[arg-type]
        schema_version=row["schema_version"],  # type: ignore[arg-type]
        payload=row["payload"],  # type: ignore[arg-type]
        metadata=row["metadata"],  # type: ignore[arg-type]
        correlation_id=UUID(row["correlation_id"]),  # type: ignore[arg-type]
        causation_id=UUID(row["causation_id"]) if row["causation_id"] else None,  # type: ignore[arg-type]
        occurred_at=datetime.fromisoformat(row["occurred_at"]),  # type: ignore[arg-type]
        recorded_at=datetime.fromisoformat(row["recorded_at"]),  # type: ignore[arg-type]
        transaction_id=int(row["transaction_id"]),  # type: ignore[arg-type]
        principal_id=UUID(row["principal_id"]) if row["principal_id"] else None,  # type: ignore[arg-type]
        signature=bytes.fromhex(row["signature"]) if row["signature"] else None,  # type: ignore[arg-type]
        signature_kid=row["signature_kid"],  # type: ignore[arg-type]
        signature_version=row["signature_version"],  # type: ignore[arg-type]
    )


async def _read_activity_rows(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT event_id, procedure_id, logbook_id, step_kind, payload,
                   sampled_at, occurred_at, recorded_at
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1
            ORDER BY sampled_at, event_id
            """,
            procedure_id,
        )


@pytest.mark.integration
async def test_procedure_stream_folds_to_running_with_activity_rows_beside_it(
    db_pool: asyncpg.Pool,
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-0000020a0a01")
    logbook_id = UUID("01900000-0000-7000-8000-0000020a0a02")
    open_event_id = UUID("01900000-0000-7000-8000-0000020a0a03")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    await _seed_running_procedure(deps.event_store, procedure_id)

    step_store = PostgresActivityStore(db_pool)
    handler = bind_append(deps, step_store=step_store)
    sampled_a = datetime(2026, 5, 15, 12, 0, 1, tzinfo=_UTC)
    sampled_b = datetime(2026, 5, 15, 12, 0, 2, tzinfo=_UTC)
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=UUID("01900000-0000-7000-8000-0000020a0b01"),
                    step_kind="setpoint",
                    payload={"channel": "T_oven", "target_value": 423.0},
                    sampled_at=sampled_a,
                ),
                ActivityInput(
                    event_id=UUID("01900000-0000-7000-8000-0000020a0b02"),
                    step_kind="check",
                    payload={"channel": "T_oven", "passed": True},
                    sampled_at=sampled_b,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        result = await export_record(pg_conn)

    procedure_rows = [row for row in result.streams if row["stream_id"] == str(procedure_id)]
    assert len(procedure_rows) == 3  # Registered, Started, ActivitiesLogbookOpened
    procedure_rows.sort(key=lambda row: int(row["version"]))  # type: ignore[arg-type]
    stored = [_stored_event_from_rendered_row(row) for row in procedure_rows]
    state = fold([from_stored(s) for s in stored])
    assert state is not None
    assert state.status == ProcedureStatus.RUNNING
    assert state.activity_logbook_id == logbook_id

    exported_activity_rows = result.logbooks["activity"]
    assert len(exported_activity_rows) == 2
    live_rows = await _read_activity_rows(db_pool, procedure_id)
    assert {row["event_id"] for row in exported_activity_rows} == {
        str(row["event_id"]) for row in live_rows
    }
    by_kind = {row["step_kind"]: row for row in exported_activity_rows}
    assert by_kind["setpoint"]["payload"] == {"channel": "T_oven", "target_value": 423.0}
    assert by_kind["check"]["payload"] == {"channel": "T_oven", "passed": True}
    # Unfolded: two distinct rows, not a summary of the logbook.
    assert by_kind["setpoint"] is not by_kind["check"]


@pytest.mark.integration
async def test_unknown_stream_type_refuses_rather_than_skips(db_pool: asyncpg.Pool) -> None:
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        await pg_conn.execute(
            """
            INSERT INTO events (event_id, stream_type, stream_id, version,
                                 event_type, payload, correlation_id, occurred_at)
            VALUES ($1, 'Widget', $2, 1, 'WidgetRegistered', '{}'::jsonb, $3, now())
            """,
            uuid4(),
            uuid4(),
            uuid4(),
        )
        with pytest.raises(UnknownStreamTypeError) as excinfo:
            await export_record(pg_conn)
    assert excinfo.value.stream_type == "Widget"


@pytest.mark.integration
async def test_zero_rows_exported_is_an_error(db_pool: asyncpg.Pool) -> None:
    """A freshly migrated template is NOT empty: two seed migrations
    (`20260519000000_seed_bootstrap_policy.sql`,
    `20260519200000_seed_default_surfaces_and_v2_policy.sql`) insert
    bootstrap events. Emptying `events` explicitly is what actually
    exercises the zero-rows refusal, on this test's own disposable
    per-test database."""
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        await pg_conn.execute("DELETE FROM events")
        with pytest.raises(EmptyExportError):
            await export_record(pg_conn)


async def _current_transaction_id(conn: asyncpg.Connection) -> int:
    """Consumes one transaction id by calling it, per `pg_current_xact_id`'s
    own documented behavior ("assigns a new one if the current transaction
    does not have one yet"). No table write needed to burn an id."""
    value = await conn.fetchval("SELECT pg_current_xact_id()::text")
    assert value is not None, "pg_current_xact_id() returned NULL outside a transaction"
    return int(value)


async def _advance_to_transaction_id(db_pool: asyncpg.Pool, target: int) -> None:
    """Burns throwaway transactions on freshly-acquired connections until
    the NEXT transaction on this database will be assigned `target`.
    Each `db_pool.acquire()` round trip is its own implicit transaction,
    so one `_current_transaction_id` call per iteration is one xid."""
    while True:
        async with db_pool.acquire() as conn:
            pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
            current = await _current_transaction_id(pg_conn)
        if current >= target - 1:
            return


@pytest.mark.integration
async def test_stream_rows_order_by_transaction_id_numerically_across_a_digit_boundary(
    db_pool: asyncpg.Pool,
) -> None:
    """Regression for a real defect caught 2026-08-25 by
    `cora.api.record_fidelity_check` against arcturus's live database: a
    Run whose two events straddled the 7-to-8-digit transaction_id
    boundary exported with the LATER event first, because `_STREAM_SQL`'s
    unqualified `ORDER BY transaction_id` resolves to the `::text` OUTPUT
    alias (Postgres's documented "output column name wins" rule), sorting
    lexicographically rather than numerically: `"10001137"` sorts before
    `"9995093"`.

    Reproduced here without waiting for ten million real transactions: a
    fresh per-test database's own transaction counter is already small, so
    burning it up to the very next power-of-ten boundary (e.g. 99 -> 100)
    is the SAME class of defect, digit-count parity intact. `procedure_id`
    is minted before the burn loop and stays fixed; only the two events'
    OWN append transactions are timed to land on `boundary - 1` and
    `boundary`.
    """
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        current = await _current_transaction_id(pg_conn)
    boundary = 10 ** len(str(current + 1))
    await _advance_to_transaction_id(db_pool, boundary - 1)

    await _seed_running_procedure(deps.event_store, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        seeded = await pg_conn.fetch(
            "SELECT event_type, transaction_id::text AS tx FROM events "
            "WHERE stream_id = $1 ORDER BY position",
            procedure_id,
        )
        record = await export_record(pg_conn)

    seeded_tx_ids = [int(row["tx"]) for row in seeded]
    assert len(seeded_tx_ids) == 2
    assert seeded_tx_ids[0] == boundary - 1
    assert seeded_tx_ids[1] == boundary
    assert len(str(seeded_tx_ids[0])) < len(str(seeded_tx_ids[1])), (
        "the burn loop must land the two events on opposite sides of a "
        "digit-count boundary, or this test exercises nothing"
    )

    this_stream = [row for row in record.streams if row["stream_id"] == str(procedure_id)]
    assert [row["event_type"] for row in this_stream] == [
        "ProcedureRegistered",
        "ProcedureStarted",
    ], (
        "ProcedureStarted (the later, higher-transaction_id event) sorted "
        "before ProcedureRegistered: the lexicographic ORDER BY defect is back"
    )
