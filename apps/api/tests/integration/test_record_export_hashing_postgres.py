"""Acceptance test for Step 3 of the record exporter build brief.

Per `project_record_export_build_brief.md` step 3: same DB exported
twice, identical hash; a flipped byte fails.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import ExportedRecord, export_record, hash_record
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure_with_activity(db_pool: asyncpg.Pool, procedure_id: UUID) -> None:
    logbook_id = uuid4()
    open_event_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[logbook_id, open_event_id])

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
        await deps.event_store.append(
            stream_type="Procedure",
            stream_id=procedure_id,
            expected_version=index,
            events=[new_event],
        )

    handler = bind_append(deps, step_store=PostgresActivityStore(db_pool))
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="setpoint",
                    payload={"channel": "T_oven", "target_value": 423.0},
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_same_database_exported_twice_hashes_identically(db_pool: asyncpg.Pool) -> None:
    await _seed_running_procedure_with_activity(db_pool, uuid4())

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        first = await export_record(pg_conn)
    async with db_pool.acquire() as conn:
        pg_conn = conn  # type: ignore[assignment]
        second = await export_record(pg_conn)

    assert hash_record(first) == hash_record(second)


@pytest.mark.integration
async def test_a_flipped_byte_in_the_exported_record_changes_the_hash(
    db_pool: asyncpg.Pool,
) -> None:
    await _seed_running_procedure_with_activity(db_pool, uuid4())

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    baseline_hash = hash_record(exported)

    tampered_first_row = dict(exported.streams[0])
    original_event_type = tampered_first_row["event_type"]
    assert isinstance(original_event_type, str) and original_event_type
    # Flip exactly one character of one field.
    tampered_first_row["event_type"] = original_event_type[:-1] + (
        "X" if original_event_type[-1] != "X" else "Y"
    )
    tampered = ExportedRecord(
        streams=(tampered_first_row, *exported.streams[1:]),
        logbooks=exported.logbooks,
    )

    assert hash_record(tampered) != baseline_hash
