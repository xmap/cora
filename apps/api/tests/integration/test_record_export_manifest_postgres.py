"""Manifest built from a real `export_record` result, not synthetic fixtures.

`build_manifest` itself is pure and unit-tested against hand-built
`ExportedRecord`s in `tests/unit/infrastructure/record_export/test_manifest.py`.
This test exists because a real rendered row's shape could diverge from
those synthetic fixtures in ways only a live export would surface (e.g.
if `event_type_name()` or `to_payload()` ever changed a key name).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import (
    build_manifest,
    capture_git_commit,
    export_record,
    hash_record,
)
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


@pytest.mark.integration
async def test_manifest_built_from_a_real_export(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
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

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    manifest = build_manifest(exported, watermark=1, git_commit=capture_git_commit())

    assert manifest.record_hash == hash_record(exported)
    assert len(manifest.redaction_profile_hash) == 64
    assert manifest.row_count_by_logbook_kind["activity"] == 1
    assert manifest.max_schema_version_by_event_type["ProcedureRegistered"] >= 1
    # No Run stream in this fixture (parent_run_id=None, no RunStarted
    # seeded), so the per-run map must be empty, not crash.
    assert manifest.expansion_digest_presence_by_run == {}
    # No observation rows in this fixture: vacuously simulated.
    assert manifest.is_simulated is True
