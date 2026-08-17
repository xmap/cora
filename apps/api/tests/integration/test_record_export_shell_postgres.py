"""Regression test for the snapshot bug `export_bundle` closes.

Per `project_record_completeness_design.md`'s "Snapshot: a prerequisite,
and a pre-existing bug": `export_record`'s per-kind entries reads carry
no watermark and no enclosing transaction, so under READ COMMITTED a
write landing between two of its queries can tear the exported record.
`export_bundle` wraps the whole export in one `REPEATABLE READ READ
ONLY` transaction to close that gap.

This test forces the race deterministically instead of relying on real
scheduling luck: it monkeypatches the "activity" registry entry
`_export.py` resolves mid-walk so that kind's entries read blocks on an
`asyncio.Event` the test controls, inserts a second activity row from a
second connection while the export is paused there, then releases it.
Without the enclosing transaction the entries query runs strictly after
the second connection's commit and would see both rows; `export_bundle`
must return only the one that existed when its snapshot was fixed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

import cora.infrastructure.record_export._export as _export_module
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import export_bundle
from cora.infrastructure.record_export._registry import resolve as real_resolve
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


async def _register_running_procedure(db_pool: asyncpg.Pool, procedure_id: UUID) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)
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


async def _append_one_activity(
    db_pool: asyncpg.Pool,
    procedure_id: UUID,
    *,
    target_value: float,
    ids: list[UUID] | None = None,
) -> None:
    """Appends one activity row. Passing `ids` opens the activities
    logbook first (needs a logbook id + an event id for the envelope);
    omitting it assumes the logbook is already open, in which case the
    handler writes only the entries row and touches no stream."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=ids)
    handler = bind_append(deps, step_store=PostgresActivityStore(db_pool))
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="setpoint",
                    payload={"channel": "T_oven", "target_value": target_value},
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_export_bundle_snapshot_hides_a_concurrent_mid_export_insert(
    db_pool: asyncpg.Pool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    open_event_id = uuid4()
    await _register_running_procedure(db_pool, procedure_id)
    await _append_one_activity(
        db_pool, procedure_id, target_value=423.0, ids=[logbook_id, open_event_id]
    )

    entries_query_started = asyncio.Event()
    release_entries_query = asyncio.Event()

    def _patched_resolve(kind: str):
        spec = real_resolve(kind)
        if kind != "activity":
            return spec

        async def _guarded_reader(conn: asyncpg.Connection, scope_id: UUID | str):
            entries_query_started.set()
            await release_entries_query.wait()
            return await spec.reader(conn, scope_id)

        return replace(spec, reader=_guarded_reader)

    monkeypatch.setattr(_export_module, "resolve", _patched_resolve)

    async def _run_export() -> Path:
        async with db_pool.acquire() as conn:
            pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
            return await export_bundle(pg_conn, tmp_path / "bundle")

    export_task = asyncio.create_task(_run_export())
    await entries_query_started.wait()

    # Committed on a second connection while the export's "activity"
    # entries read is paused mid-flight, waiting on release_entries_query.
    await _append_one_activity(db_pool, procedure_id, target_value=999.0)

    release_entries_query.set()
    bundle = await export_task

    activity_lines = (
        (bundle / "logbooks" / "activity.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(activity_lines) == 1, (
        "export_bundle's REPEATABLE READ snapshot must hide a row committed "
        "after the snapshot was fixed, even though it landed before the "
        "entries query actually ran"
    )
    assert json.loads(activity_lines[0])["payload"]["target_value"] == 423.0
