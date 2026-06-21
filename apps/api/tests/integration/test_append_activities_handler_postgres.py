"""End-to-end integration test: append_activities against real Postgres.

First concrete consumer of the entries_operation_procedure_activities
table + PostgresActivityStore. Stress-tests the polymorphic-with-
discriminator + JSON-payload storage shape + lazy open-on-first-
write + dedup-on-event_id + three-timestamp round-trip against
actual Postgres semantics (jsonb payload column, plain TEXT
discriminator, BRIN index on recorded_at).

Mirrors `test_append_observations_handler_postgres.py` shape exactly.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.features.append_activities import (
    ActivityInput,
    AppendProcedureActivities,
)
from cora.operation.features.append_activities import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    """Seed Registered + Started events directly into the event store.

    Bypasses register_procedure + start_procedure handlers (which
    have their own cross-aggregate validation paths) so the test
    focuses on the step-append + lazy-open path against Postgres.
    """
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
        await deps_event_store.append(  # type: ignore[attr-defined]
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=index,
            events=[new_event],
        )


async def _read_steps_for_procedure(
    db_pool: asyncpg.Pool, procedure_id: UUID
) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT
                event_id, procedure_id, logbook_id, actor_id, command_name,
                step_kind, payload, sampled_at, occurred_at, recorded_at,
                correlation_id, causation_id
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1
            ORDER BY sampled_at, event_id
            """,
            procedure_id,
        )


def _entry(
    *,
    event_id: UUID,
    step_kind: str,
    payload: dict[str, object],
    sampled_at: datetime,
) -> ActivityInput:
    return ActivityInput(
        event_id=event_id,
        step_kind=step_kind,
        payload=payload,
        sampled_at=sampled_at,
    )


@pytest.mark.integration
async def test_append_activities_lazy_open_and_polymorphic_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: seed a Procedure, then append a 3-entry polymorphic batch
    (setpoint + action + check). Verify lazy ProcedureActivitiesLogbookOpened
    landed on the Procedure stream, all 3 rows landed in
    entries_operation_procedure_activities with the correct discriminator + JSON
    payload + sampled_at preserved, and a follow-up append on the same
    Procedure skips the open + appends to the same logbook."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010c0b01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010c0b02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010c0b03")
    setpoint_id = UUID("01900000-0000-7000-8000-0000010c0c01")
    action_id = UUID("01900000-0000-7000-8000-0000010c0c02")
    check_id = UUID("01900000-0000-7000-8000-0000010c0c03")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    step_store = PostgresActivityStore(db_pool)

    await _seed_running_procedure(deps.event_store, procedure_id)

    sampled_a = datetime(2026, 5, 15, 12, 0, 1, tzinfo=UTC)
    sampled_b = datetime(2026, 5, 15, 12, 0, 2, tzinfo=UTC)
    sampled_c = datetime(2026, 5, 15, 12, 0, 3, tzinfo=UTC)

    handler = bind_append(deps, step_store=step_store)
    count = await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=setpoint_id,
                    step_kind="setpoint",
                    payload={
                        "channel": "T_oven",
                        "target_value": 423.0,
                        "units": "K",
                        "ramp_rate": 5.0,
                    },
                    sampled_at=sampled_a,
                ),
                _entry(
                    event_id=action_id,
                    step_kind="action",
                    payload={"action_name": "open_valve", "params": {"valve": "V12"}},
                    sampled_at=sampled_b,
                ),
                _entry(
                    event_id=check_id,
                    step_kind="check",
                    payload={
                        "channel": "T_oven",
                        "passed": True,
                        "expected": 423.0,
                        "actual": 422.8,
                        "tolerance": 1.0,
                    },
                    sampled_at=sampled_c,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 3

    # Procedure stream gained the lazy-open envelope event at v3.
    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 3
    assert events[2].event_type == "ProcedureActivitiesLogbookOpened"
    # Open-event payload roundtripped through Postgres jsonb cleanly:
    open_payload = events[2].payload
    assert open_payload["procedure_id"] == str(procedure_id)
    assert open_payload["logbook_id"] == str(logbook_id)
    assert open_payload["kind"] == "activity"
    assert "schema" in open_payload  # full schema dict serialized
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.activity_logbook_id == logbook_id

    # entries table has the 3 rows with correct discriminators + JSON payloads.
    rows = await _read_steps_for_procedure(db_pool, procedure_id)
    assert len(rows) == 3
    by_kind = {r["step_kind"]: r for r in rows}
    assert set(by_kind) == {"setpoint", "action", "check"}

    setpoint_row = by_kind["setpoint"]
    assert setpoint_row["procedure_id"] == procedure_id
    assert setpoint_row["logbook_id"] == logbook_id
    assert setpoint_row["actor_id"] == _PRINCIPAL_ID
    assert setpoint_row["correlation_id"] == _CORRELATION_ID
    assert setpoint_row["command_name"] == "AppendProcedureActivities"
    # Three-timestamp pattern (project_logbook_entry_storage):
    assert setpoint_row["sampled_at"] == sampled_a  # phenomenonTime
    assert setpoint_row["occurred_at"] == _NOW  # Clock port (handler-time)
    # recorded_at is DEFAULT now() at the DB layer; must come AFTER occurred_at.
    assert setpoint_row["recorded_at"] >= setpoint_row["occurred_at"]
    # asyncpg returns jsonb as a JSON string for plain SELECT; decode it.
    setpoint_payload = setpoint_row["payload"]
    assert setpoint_payload == {
        "channel": "T_oven",
        "target_value": 423.0,
        "units": "K",
        "ramp_rate": 5.0,
    }

    action_payload = by_kind["action"]["payload"]
    assert action_payload == {"action_name": "open_valve", "params": {"valve": "V12"}}

    check_payload = by_kind["check"]["payload"]
    assert check_payload["passed"] is True
    assert check_payload["actual"] == 422.8

    # Second append on the same Procedure: should skip the open event
    # (logbook already attached) but land additional rows in the same
    # logbook.
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    handler2 = bind_append(deps2, step_store=step_store)
    second_id = UUID("01900000-0000-7000-8000-0000010c0c04")
    second_sampled = datetime(2026, 5, 15, 12, 0, 5, tzinfo=UTC)
    await handler2(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=second_id,
                    step_kind="check",
                    payload={"channel": "T_oven", "passed": True},
                    sampled_at=second_sampled,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Stream still at v3 (no second open emitted).
    events, version = await deps2.event_store.load("Procedure", procedure_id)
    assert version == 3
    open_count = sum(1 for e in events if e.event_type == "ProcedureActivitiesLogbookOpened")
    assert open_count == 1
    # entries table has 4 rows now, all in the same logbook.
    all_rows = await _read_steps_for_procedure(db_pool, procedure_id)
    assert len(all_rows) == 4
    assert {r["logbook_id"] for r in all_rows} == {logbook_id}


@pytest.mark.integration
async def test_append_activities_dedups_on_event_id_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Producer retry with same event_id: ON CONFLICT DO NOTHING silently."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010c0d01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010c0d02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010c0d03")
    eid = UUID("01900000-0000-7000-8000-0000010c0d11")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    step_store = PostgresActivityStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, step_store=step_store)
    sampled_at = datetime(2026, 5, 15, 12, 0, 1, tzinfo=UTC)
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=eid,
                    step_kind="setpoint",
                    payload={"channel": "X", "target_value": 1.0},
                    sampled_at=sampled_at,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Re-issue with the SAME event_id but a different body shape.
    deps2 = build_postgres_deps(db_pool, now=_NOW, ids=[])
    await bind_append(deps2, step_store=step_store)(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=eid,
                    step_kind="action",
                    payload={"action_name": "retry"},
                    sampled_at=sampled_at,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Only one row persisted; first wins per ON CONFLICT DO NOTHING.
    rows = await _read_steps_for_procedure(db_pool, procedure_id)
    assert len(rows) == 1
    assert rows[0]["step_kind"] == "setpoint"
    payload = rows[0]["payload"]
    assert payload == {"channel": "X", "target_value": 1.0}


@pytest.mark.integration
async def test_postgres_step_store_handles_empty_batch(db_pool: asyncpg.Pool) -> None:
    """Empty batch is a no-op at the adapter layer (early return)."""
    store = PostgresActivityStore(db_pool)
    await store.append([])  # No exception, no rows touched.


@pytest.mark.integration
async def test_payload_stores_as_real_jsonb_so_server_side_filters_work(
    db_pool: asyncpg.Pool,
) -> None:
    """Regression: payload must persist as a real jsonb OBJECT (not a double-
    encoded jsonb scalar string), so server-side `payload->>'key'` works. When
    payload was double-encoded (json.dumps bound to a jsonb column with no
    `::jsonb` cast), `payload->>'result'` returned NULL and the conductor's
    in-flight-marker filters (`payload->>'result' IS DISTINCT FROM 'in_flight'`)
    silently no-op'd, leaking marker rows into assertions."""
    procedure_id = UUID("01900000-0000-7000-8000-0000010c0d01")
    logbook_id = UUID("01900000-0000-7000-8000-0000010c0d02")
    open_event_id = UUID("01900000-0000-7000-8000-0000010c0d03")
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])
    step_store = PostgresActivityStore(db_pool)
    await _seed_running_procedure(deps.event_store, procedure_id)

    handler = bind_append(deps, step_store=step_store)
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                _entry(
                    event_id=UUID("01900000-0000-7000-8000-0000010c0e01"),
                    step_kind="setpoint",
                    payload={"address": "2bma:x", "result": "in_flight"},
                    sampled_at=datetime(2026, 5, 15, 12, 0, 1, tzinfo=UTC),
                ),
                _entry(
                    event_id=UUID("01900000-0000-7000-8000-0000010c0e02"),
                    step_kind="setpoint",
                    payload={"address": "2bma:x", "result": "ok"},
                    sampled_at=datetime(2026, 5, 15, 12, 0, 2, tzinfo=UTC),
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        # Server-side extraction returns the actual value (not NULL), so the
        # marker filter excludes the in_flight row and keeps only the outcome.
        rows = await conn.fetch(
            """
            SELECT payload->>'result' AS result
            FROM entries_operation_procedure_activities
            WHERE procedure_id = $1 AND payload->>'result' IS DISTINCT FROM 'in_flight'
            """,
            procedure_id,
        )
    assert [r["result"] for r in rows] == ["ok"]
