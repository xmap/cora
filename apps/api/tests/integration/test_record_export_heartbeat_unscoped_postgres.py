"""S5a exit criteria: `heartbeat` is read into the record via an unscoped
whole-table select, its extent status flips to `included`, and the read
is proven genuinely unscoped rather than merely argued from the SQL text.

Per `project_record_completeness_design.md`'s S5. `capture_probe` was
S5b's own probe kind and carries the identical assertion, in
`test_record_export_capture_probe_unscoped_postgres.py`; `permit_probe`
was S5c's, in `test_record_export_permit_probe_unscoped_postgres.py`.
Before S5c landed, this file also pinned `permit_probe` staying
`untraversed` with rows present; that assertion is gone along with the
state it pinned (no registered kind resolves `untraversed` in production
once all three no-envelope kinds are wired) -- see
`test_manifest.py`'s `test_kind_with_no_envelope_and_no_unscoped_reader_is_untraversed`
for where that predicate is still exercised, deliberately, against a
synthetic spec.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.record_export import export_bundle
from cora.run.aggregates.run import FeedHeartbeat, PostgresFeedHeartbeatStore

_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


async def _export(db_pool: asyncpg.Pool, tmp_path: Path) -> Path:
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        return await export_bundle(pg_conn, tmp_path / "bundle")


@pytest.mark.integration
async def test_heartbeat_rows_land_in_the_bundle_and_manifest_reports_included(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """Seeded through the real production writer
    (`PostgresFeedHeartbeatStore.append`, the same call
    `CaptureProgressFeeder`/`RunTranslator` make -- there is no CQRS
    handler wrapper for this table, see `feed_heartbeats.py`)."""
    store = PostgresFeedHeartbeatStore(db_pool)
    run_id = uuid4()
    await store.append(
        [FeedHeartbeat(event_id=uuid4(), run_id=run_id, source_id="epics", heartbeat_at=_NOW)]
    )

    bundle = await _export(db_pool, tmp_path)

    heartbeat_path = bundle / "logbooks" / "heartbeat.jsonl"
    rows = [json.loads(line) for line in heartbeat_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["run_id"] == str(run_id)
    assert rows[0]["source_id"] == "epics"

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extent_by_logbook_kind"]["heartbeat"]["status"] == "included"
    heartbeat_extent = manifest["extent_by_logbook_kind"]["heartbeat"]
    assert heartbeat_extent["exported_row_count"] == 1
    assert heartbeat_extent["source_row_count"] == 1


@pytest.mark.integration
async def test_heartbeat_unscoped_read_returns_rows_across_different_run_ids(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The differential check per `project_independent_check_principle.md`:
    a structural argument ("the SQL has no WHERE clause") proves nothing
    on its own. A reader accidentally still scoped to one `run_id` would
    return only that run's row; seeding two DIFFERENT `run_id`s and
    asserting both come back is what actually exercises the absence of a
    predicate."""
    store = PostgresFeedHeartbeatStore(db_pool)
    run_id_a, run_id_b = uuid4(), uuid4()
    await store.append(
        [
            FeedHeartbeat(
                event_id=uuid4(), run_id=run_id_a, source_id="epics-a", heartbeat_at=_NOW
            ),
            FeedHeartbeat(
                event_id=uuid4(), run_id=run_id_b, source_id="epics-b", heartbeat_at=_NOW
            ),
        ]
    )

    bundle = await _export(db_pool, tmp_path)

    heartbeat_path = bundle / "logbooks" / "heartbeat.jsonl"
    run_ids_present = {
        json.loads(line)["run_id"]
        for line in heartbeat_path.read_text(encoding="utf-8").splitlines()
    }
    assert {str(run_id_a), str(run_id_b)} <= run_ids_present
