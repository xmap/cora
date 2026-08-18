"""S5b exit criteria: `capture_probe` is read into the record via an
unscoped whole-table select, its extent status flips to `included`, the
read is proven genuinely unscoped rather than merely argued from the SQL
text, and its tier-2 dispositions -- declared since before this slice but
never exercised, because `_redact_tier2.py` skips a kind absent from
`kinds_present` -- fire for the first time on a real exported row.

Per `project_record_completeness_design.md`'s S5. `permit_probe` was
S5c's own probe kind and carries the identical assertion, in
`test_record_export_permit_probe_unscoped_postgres.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.record_export import (
    export_bundle,
    export_record,
    hash_redaction_profile,
    redact_record,
)
from cora.run.aggregates.run import CaptureProbe, PostgresCaptureProbeStore
from cora.shared.reach import ReachTier

_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


async def _export(db_pool: asyncpg.Pool, tmp_path: Path) -> Path:
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        return await export_bundle(pg_conn, tmp_path / "bundle")


def _capture_probe(
    *, capture_code: str, source_id: str = "2bmb:TomoScan:ScanStatus"
) -> CaptureProbe:
    return CaptureProbe(
        event_id=uuid4(),
        capture_code=capture_code,
        source_kind="EpicsPv",
        source_id=source_id,
        reach_tier=ReachTier.RELAYED,
        phase_claimed=True,
        observed_at=_NOW,
    )


@pytest.mark.integration
async def test_capture_probe_rows_land_in_the_bundle_and_manifest_reports_included(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """Seeded through the real production writer
    (`PostgresCaptureProbeStore.append`; `capture_code` has no backing
    aggregate, so there is no CQRS handler wrapper for this table, same
    as `heartbeat`)."""
    store = PostgresCaptureProbeStore(db_pool)
    capture_code = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    await store.append([_capture_probe(capture_code=capture_code)])

    bundle = await _export(db_pool, tmp_path)

    capture_probe_path = bundle / "logbooks" / "capture_probe.jsonl"
    rows = [
        json.loads(line) for line in capture_probe_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["capture_code"] == capture_code
    assert rows[0]["source_id"] == "2bmb:TomoScan:ScanStatus"

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extent_by_logbook_kind"]["capture_probe"]["status"] == "included"
    assert manifest["row_count_by_logbook_kind"]["capture_probe"] == 1


@pytest.mark.integration
async def test_capture_probe_unscoped_read_returns_rows_across_different_capture_codes(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The differential check per `project_independent_check_principle.md`:
    a structural argument ("the SQL has no WHERE clause") proves nothing
    on its own. A reader accidentally still scoped to one `capture_code`
    would return only that code's rows; seeding two DIFFERENT
    `capture_code` values and asserting both come back is what actually
    exercises the absence of a predicate."""
    store = PostgresCaptureProbeStore(db_pool)
    code_a = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    code_b = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    await store.append([_capture_probe(capture_code=code_a), _capture_probe(capture_code=code_b)])

    bundle = await _export(db_pool, tmp_path)

    capture_probe_path = bundle / "logbooks" / "capture_probe.jsonl"
    codes_present = {
        json.loads(line)["capture_code"]
        for line in capture_probe_path.read_text(encoding="utf-8").splitlines()
    }
    assert {code_a, code_b} <= codes_present


@pytest.mark.integration
async def test_capture_probe_tier2_dispositions_fire_on_a_real_exported_row(
    db_pool: asyncpg.Pool,
) -> None:
    """Before this slice, `capture_probe` never appeared in
    `record.logbooks` (no reader reached it), so `redact_tier2_row` never
    ran for this kind in production and its disposition table -- one
    TOKEN, six KEEPs, one DROP (`phase_claimed`, reversed from an earlier
    KEEP during this slice's own gate review) -- was declared but
    untested. This is that first exercise: `event_id` tokenizes,
    `phase_claimed` drops, every other declared column survives
    unchanged."""
    store = PostgresCaptureProbeStore(db_pool)
    probe = _capture_probe(capture_code=f"2bmb-tomoscan-{uuid4().hex[:8]}")
    await store.append([probe])

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    result = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    rows = result.redacted_record.logbooks["capture_probe"]
    matching = [row for row in rows if row["capture_code"] == probe.capture_code]
    assert len(matching) == 1
    row = matching[0]

    assert row["event_id"] != str(probe.event_id)
    assert row["event_id"] == result.token_map.surrogate_by_source[str(probe.event_id)]

    assert row["capture_code"] == probe.capture_code
    assert row["source_kind"] == probe.source_kind
    assert row["source_id"] == probe.source_id
    assert row["reach_tier"] == probe.reach_tier.value
    assert "phase_claimed" not in row
    assert probe.observed_at is not None
    assert row["observed_at"] == probe.observed_at.astimezone(UTC).isoformat()
    assert "recorded_at" in row
