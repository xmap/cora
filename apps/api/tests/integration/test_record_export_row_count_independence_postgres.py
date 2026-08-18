"""S2b's exit criterion: the independent row count proven DIFFERENTIALLY,
on both shapes the registry actually has.

Per `project_record_completeness_design.md`'s "The independent count" and
`project_independent_check_principle.md`: a structural argument ("the two
queries share no predicate") proves nothing on its own. This file seeds a
real discrepancy the exporter's own traversal cannot see and asserts the
export refuses, for the ENVELOPE-scoped shape (`activity`) -- then attempts
the identical trick against an UNSCOPED kind (`heartbeat`) and confirms it
is impossible under this design's shared-snapshot guarantee, per the
design's own explicit allowance: "if you cannot construct a discrepancy...
say so; that is a finding, not a failure." `test_heartbeat_render_stage_row_loss_still_raises`
below then proves the axis that DOES apply to an unscoped kind (a row lost
between fetch and render) live, through a real `export_bundle` call, not
just against a hand-built `ExportedRecord`
(`tests/unit/infrastructure/record_export/test_manifest.py`'s sibling unit
tests cover the same shape at the unit level, cheaply, for every kind).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import (
    LogbookKindRowCountMismatchError,
    all_specs,
    export_bundle,
    resolve,
)
from cora.operation.aggregates.procedure import (
    Activity,
    PostgresActivityStore,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)
from cora.operation.features.append_activities import ActivityInput, AppendProcedureActivities
from cora.operation.features.append_activities import bind as bind_append
from cora.run.aggregates.run import FeedHeartbeat, PostgresFeedHeartbeatStore
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_running_procedure(event_store: object, procedure_id: UUID) -> None:
    """Same shape as `test_record_export_shell_postgres.py`'s helper:
    `ProcedureRegistered` + `ProcedureStarted` appended directly, bypassing
    cross-aggregate validation this test doesn't need."""
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


@pytest.mark.integration
async def test_orphan_activity_row_diverges_the_independent_count_and_export_refuses(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """`activity` is envelope-scoped (`scope_column="logbook_id"`, reached
    only by following a `ProcedureActivitiesLogbookOpened` envelope). One
    row is written through the real production path (handler opens the
    envelope and writes the entry atomically); a second is written by
    calling `PostgresActivityStore.append` directly with a `logbook_id`
    that never appears in any envelope on the stream -- simulating the
    exact class of defect this design exists to catch (a row the database
    holds that the traversal has no way to reach). `source_row_count`
    (unscoped `count(*)`) sees both; `exported_row_count` (the envelope
    walk) sees only the first, so `export_bundle` must refuse."""
    procedure_id = uuid4()
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4(), uuid4()])
    await _seed_running_procedure(deps.event_store, procedure_id)
    await bind_append(deps, step_store=PostgresActivityStore(db_pool))(
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

    orphan_logbook_id = uuid4()
    await PostgresActivityStore(db_pool).append(
        [
            Activity(
                event_id=uuid4(),
                procedure_id=uuid4(),
                logbook_id=orphan_logbook_id,
                actor_id=uuid4(),
                command_name="AppendProcedureActivities",
                step_kind="setpoint",
                payload={"channel": "T_orphan", "target_value": 1.0},
                sampled_at=_NOW,
                occurred_at=_NOW,
                correlation_id=uuid4(),
                causation_id=None,
            )
        ]
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
            await export_bundle(pg_conn, tmp_path / "bundle")

    assert excinfo.value.kind == "activity"
    assert excinfo.value.source_row_count == 2
    assert excinfo.value.exported_row_count == 1
    # No bundle directory left half-written: build_manifest raises before
    # write_bundle is ever called.
    assert not (tmp_path / "bundle").exists()


@pytest.mark.integration
async def test_unscoped_heartbeat_rows_cannot_diverge_under_the_shared_snapshot(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The negative half of the finding: `heartbeat` has no envelope, so
    `spec.unscoped_reader` and `capture_source_row_count_by_logbook_kind` run the
    IDENTICAL `SELECT ... FROM entries_run_feed_heartbeats` shape (one
    unscoped, one `count(*)`) inside the SAME `REPEATABLE READ` snapshot.
    There is no seeding trick at the database level that makes these two
    disagree -- attempting the same "write a row outside the normal path"
    technique as the envelope test above only proves the obvious: every
    row in this table is unconditionally in scope for both queries.
    Real independence for this kind lives at a different axis entirely
    (a row lost between fetch and render), proven live below in
    `test_heartbeat_render_stage_row_loss_still_raises`."""
    store = PostgresFeedHeartbeatStore(db_pool)
    await store.append(
        [
            FeedHeartbeat(event_id=uuid4(), run_id=uuid4(), source_id="epics-a", heartbeat_at=_NOW),
            FeedHeartbeat(event_id=uuid4(), run_id=uuid4(), source_id="epics-b", heartbeat_at=_NOW),
        ]
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        bundle = await export_bundle(pg_conn, tmp_path / "bundle")

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    heartbeat_extent = manifest["extent_by_logbook_kind"]["heartbeat"]
    assert heartbeat_extent["exported_row_count"] == 2
    assert heartbeat_extent["source_row_count"] == 2


@pytest.mark.integration
async def test_heartbeat_render_stage_row_loss_still_raises(
    db_pool: asyncpg.Pool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real differential proof for the axis that DOES apply to an
    unscoped kind, live rather than hand-built: a row lost between the
    fetch and the render stage. Two heartbeat rows are seeded for real;
    the heartbeat spec's `unscoped_reader` is wrapped to silently drop one
    of the two rows it fetches, simulating a bug somewhere between the
    unscoped `SELECT` and `ExportedRecord.logbooks` -- `render_row` and
    the rest of `export_record`'s pipeline still run for real on whatever
    the wrapped reader hands back. `count_reader` is left completely
    untouched (`dataclasses.replace` only overrides `unscoped_reader`), so
    `source_row_count` still reports the true count of 2 straight from the
    database, independent of the fetch this test is sabotaging. The
    unit-level sibling in `test_manifest.py` proves the same shape against
    a hand-built `ExportedRecord`; this proves it survives a live export
    end to end, closing the gap a purely hand-built fixture cannot: that
    `render_row` and the loop in `_export.py` actually run in between."""
    store = PostgresFeedHeartbeatStore(db_pool)
    await store.append(
        [
            FeedHeartbeat(event_id=uuid4(), run_id=uuid4(), source_id="epics-a", heartbeat_at=_NOW),
            FeedHeartbeat(event_id=uuid4(), run_id=uuid4(), source_id="epics-b", heartbeat_at=_NOW),
        ]
    )

    real_spec = resolve("heartbeat")
    assert real_spec.unscoped_reader is not None
    real_unscoped_reader = real_spec.unscoped_reader

    async def _drop_one_row(conn: asyncpg.Connection) -> list[asyncpg.Record]:
        rows = await real_unscoped_reader(conn)
        return rows[:1]

    lossy_heartbeat_spec = dataclasses.replace(real_spec, unscoped_reader=_drop_one_row)
    monkeypatch.setattr(
        "cora.infrastructure.record_export._export.all_specs",
        lambda: tuple(
            lossy_heartbeat_spec if spec.kind == "heartbeat" else spec for spec in all_specs()
        ),
    )

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
            await export_bundle(pg_conn, tmp_path / "bundle")

    assert excinfo.value.kind == "heartbeat"
    assert excinfo.value.source_row_count == 2
    assert excinfo.value.exported_row_count == 1
