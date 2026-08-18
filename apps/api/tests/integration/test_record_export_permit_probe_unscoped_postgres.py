"""S5c exit criteria: `permit_probe` is read into the record via an
unscoped whole-table select, its extent status flips to `included`, the
read is proven genuinely unscoped rather than merely argued from the SQL
text, and its tier-2 dispositions -- declared since before this slice but
never exercised, because `_redact_tier2.py` skips a kind absent from
`kinds_present` -- fire for the first time on a real exported row.

Per `project_record_completeness_design.md`'s S5. `permit_probe` is the
ninth and last kind with no reader; once it lands, every registered kind
resolves `included` and no kind resolves `untraversed` in production,
pinned by `test_every_registered_kind_resolves_included` below.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure.aggregates.enclosure import PermitProbe, PostgresPermitProbeStore
from cora.infrastructure.record_export import (
    EntriesTableSpec,
    all_specs,
    export_bundle,
    export_record,
    hash_redaction_profile,
    redact_record,
)
from cora.shared.reach import ReachTier


async def _export(db_pool: asyncpg.Pool, tmp_path: Path) -> Path:
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        return await export_bundle(pg_conn, tmp_path / "bundle")


def _permit_probe(
    *,
    enclosure_id: UUID,
    source_id: str = "S02BM-PSS:StaA:SecureM",
    reach_tier: ReachTier = ReachTier.RELAYED,
    status_claimed: bool = True,
) -> PermitProbe:
    return PermitProbe(
        event_id=uuid4(),
        enclosure_id=enclosure_id,
        source_kind="EpicsPv",
        source_id=source_id,
        reach_tier=reach_tier,
        status_claimed=status_claimed,
    )


@pytest.mark.integration
async def test_permit_probe_rows_land_in_the_bundle_and_manifest_reports_included(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """Seeded through the real production writer
    (`PostgresPermitProbeStore.append`, the same call
    `cora.enclosure._monitor.record_observation` makes; there is no CQRS
    handler wrapper for this table, same as `heartbeat`/`capture_probe`)."""
    store = PostgresPermitProbeStore(db_pool)
    enclosure_id = uuid4()
    await store.append([_permit_probe(enclosure_id=enclosure_id)])

    bundle = await _export(db_pool, tmp_path)

    permit_probe_path = bundle / "logbooks" / "permit_probe.jsonl"
    rows = [json.loads(line) for line in permit_probe_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["source_kind"] == "EpicsPv"

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extent_by_logbook_kind"]["permit_probe"]["status"] == "included"
    permit_probe_extent = manifest["extent_by_logbook_kind"]["permit_probe"]
    assert permit_probe_extent["exported_row_count"] == 1
    assert permit_probe_extent["source_row_count"] == 1


@pytest.mark.integration
async def test_permit_probe_unscoped_read_returns_rows_across_different_enclosure_ids(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The differential check per `project_independent_check_principle.md`:
    a structural argument ("the SQL has no WHERE clause") proves nothing
    on its own. A reader accidentally still scoped to one `enclosure_id`
    would return only that enclosure's rows; seeding two DIFFERENT
    `enclosure_id` values and asserting both come back is what actually
    exercises the absence of a predicate."""
    store = PostgresPermitProbeStore(db_pool)
    enclosure_a, enclosure_b = uuid4(), uuid4()
    await store.append(
        [
            _permit_probe(enclosure_id=enclosure_a),
            _permit_probe(enclosure_id=enclosure_b),
        ]
    )

    bundle = await _export(db_pool, tmp_path)

    permit_probe_path = bundle / "logbooks" / "permit_probe.jsonl"
    rows = [json.loads(line) for line in permit_probe_path.read_text(encoding="utf-8").splitlines()]
    # enclosure_id tokenizes at tier-2 redaction, but export_bundle writes
    # the unredacted bundle: raw enclosure_id survives here, which is what
    # this test needs to tell the two seeded rows apart.
    enclosure_ids_present = {row["enclosure_id"] for row in rows}
    assert {str(enclosure_a), str(enclosure_b)} <= enclosure_ids_present


@pytest.mark.integration
async def test_permit_probe_tier2_dispositions_fire_on_a_real_exported_row(
    db_pool: asyncpg.Pool,
) -> None:
    """Before this slice, `permit_probe` never appeared in
    `record.logbooks` (no reader reached it), so `redact_tier2_row` never
    ran for this kind in production and its disposition table -- two
    TOKENs, three KEEPs, two DROPs -- was declared but untested. This is
    that first exercise. `status_claimed` DROPS: S5c's own verdict,
    reversed from an earlier KEEP watch item, reasoned independently of
    S5b's `capture_probe.phase_claimed` reversal because this table has
    no `observed_at` column for it to be redundant with (see
    `_redact_tier2.py`'s comment on this disposition for the full
    argument)."""
    store = PostgresPermitProbeStore(db_pool)
    probe = _permit_probe(enclosure_id=uuid4(), reach_tier=ReachTier.UNREACHED, status_claimed=True)
    await store.append([probe])

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    result = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    rows = result.redacted_record.logbooks["permit_probe"]
    matching = [row for row in rows if row["source_kind"] == probe.source_kind]
    assert len(matching) == 1
    row = matching[0]

    assert row["event_id"] != str(probe.event_id)
    assert row["event_id"] == result.token_map.surrogate_by_source[str(probe.event_id)]
    assert row["enclosure_id"] != str(probe.enclosure_id)
    assert row["enclosure_id"] == result.token_map.surrogate_by_source[str(probe.enclosure_id)]

    assert row["source_kind"] == probe.source_kind
    assert "source_id" not in row  # DROP: PSS/interlock substrate address
    assert row["reach_tier"] == probe.reach_tier.value
    assert "status_claimed" not in row  # DROP: S5c verdict, see _redact_tier2.py
    assert "recorded_at" in row


@pytest.mark.integration
async def test_every_registered_kind_resolves_included(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """Pins the "all nine in" outcome rather than leaving it incidental:
    after `permit_probe` (S5c, the last of the three no-envelope kinds)
    is wired, `all_specs()` must show every registered kind reachable by
    either an envelope or an unscoped reader, with nothing left over."""
    assert all(
        spec.envelope_class is not None or spec.unscoped_reader is not None for spec in all_specs()
    )

    store = PostgresPermitProbeStore(db_pool)
    await store.append([_permit_probe(enclosure_id=uuid4())])

    bundle = await _export(db_pool, tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    extent = manifest["extent_by_logbook_kind"]
    assert {status["status"] for status in extent.values()} == {"included"}


async def _unused_reader(conn: asyncpg.Connection, scope_id: object) -> list[asyncpg.Record]:
    raise AssertionError("an untraversed kind's reader must never be called")


async def _unused_count_reader(conn: asyncpg.Connection) -> int:
    raise AssertionError("an untraversed kind's count_reader must never be called")


@pytest.mark.integration
async def test_untraversed_status_survives_the_bundles_disk_round_trip(
    db_pool: asyncpg.Pool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`permit_probe` (S5c) was the last real kind demonstrating
    `LogbookKindExtentStatus.UNTRAVERSED` end to end; with it gone, this
    proves the StrEnum still survives `_bundle.write_bundle`'s
    `json.dumps(asdict(manifest))` round trip as the literal string
    `"untraversed"` in `manifest.json`, not just inside the in-process
    `Manifest` dataclass (`test_manifest.py`'s own construction covers
    that half; this is the disk-write half `export_bundle` actually
    exercises in production). A synthetic spec stands in for a real
    kind, same shape as `test_manifest.py`'s unit-level construction."""
    synthetic = EntriesTableSpec(
        kind="untraversed_test_kind",
        table="entries_untraversed_test_kind",
        envelope_class=None,
        scope_column="unused_id",
        scope_type=UUID,
        order_by=("event_id",),
        reader=_unused_reader,
        count_reader=_unused_count_reader,
    )
    monkeypatch.setattr(
        "cora.infrastructure.record_export._manifest.all_specs",
        lambda: (*all_specs(), synthetic),
    )

    store = PostgresPermitProbeStore(db_pool)
    await store.append([_permit_probe(enclosure_id=uuid4())])
    bundle = await _export(db_pool, tmp_path)

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    extent = manifest["extent_by_logbook_kind"]
    assert extent["untraversed_test_kind"]["status"] == "untraversed"
    assert extent["untraversed_test_kind"]["exported_row_count"] == 0
    assert extent["untraversed_test_kind"]["source_row_count"] is None
    assert not (bundle / "logbooks" / "untraversed_test_kind.jsonl").exists()
