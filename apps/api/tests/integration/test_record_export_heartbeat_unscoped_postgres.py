"""S5a exit criteria: `heartbeat` is read into the record via an unscoped
whole-table select, its extent status flips to `included`, and the read
is proven genuinely unscoped rather than merely argued from the SQL text.

Per `project_record_completeness_design.md`'s S5. `permit_probe` and
`capture_probe` are S5b/S5c, not this slice, and must stay `untraversed`
even when their tables hold rows; that is reasserted here narrowly as
this slice's own exit criterion (the general sweep already lives in
`test_manifest_extent_seeders_postgres.py`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from cora.enclosure.aggregates.enclosure import PermitProbe, PostgresPermitProbeStore
from cora.infrastructure.record_export import export_bundle
from cora.run.aggregates.run import (
    CaptureProbe,
    FeedHeartbeat,
    PostgresCaptureProbeStore,
    PostgresFeedHeartbeatStore,
)
from cora.shared.reach import ReachTier

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
    `CaptureProgressFeeder`/`RunWitnessRecorder` make -- there is no CQRS
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
    assert manifest["row_count_by_logbook_kind"]["heartbeat"] == 1


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


@pytest.mark.integration
async def test_probe_kinds_stay_untraversed_even_with_rows_present(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """S4 decided all nine registered kinds are IN, but `permit_probe` and
    `capture_probe` are S5b/S5c, deliberately not this slice: each holds
    every live entries row on the pilot database and owes its own
    disclosure review. A bundle built from a database holding their rows
    must still report both `untraversed`, which is what keeps the bundle
    not-complete rather than silently letting S4's decision read as done
    everywhere at once."""
    await PostgresPermitProbeStore(db_pool).append(
        [
            PermitProbe(
                event_id=uuid4(),
                enclosure_id=uuid4(),
                source_kind="EpicsPv",
                source_id="2bma:hutch:permit",
                reach_tier=ReachTier.RELAYED,
                status_claimed=True,
            )
        ]
    )
    await PostgresCaptureProbeStore(db_pool).append(
        [
            CaptureProbe(
                event_id=uuid4(),
                capture_code=f"2bmb-tomoscan-{uuid4().hex[:8]}",
                source_kind="EpicsPv",
                source_id="2bmb:TomoScan:ScanStatus",
                reach_tier=ReachTier.RELAYED,
                phase_claimed=True,
                observed_at=_NOW,
            )
        ]
    )

    bundle = await _export(db_pool, tmp_path)

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    extent = manifest["extent_by_logbook_kind"]
    assert extent["permit_probe"]["status"] == "untraversed"
    assert extent["capture_probe"]["status"] == "untraversed"
    assert "permit_probe" not in manifest["row_count_by_logbook_kind"]
    assert "capture_probe" not in manifest["row_count_by_logbook_kind"]
