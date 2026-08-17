"""Integration: capture-probe write against Postgres (slice 16).

Mirrors `test_enclosure_permit_monitor.py`'s own permit-probe write
test. No read-lookup counterpart exists (no read surface, mirroring
`PermitProbe`'s R15 precedent), so this reads back via a direct query,
matching that test's own shape. Verifies `observed_at` round-trips both
when set and when `NULL`, the deliberate divergence from
`entries_enclosure_permit_probes` (see `capture_probes.py`'s module
docstring), and that two PVs on one code write independent rows.

Runs against `db_pool` (the testcontainers superuser), same as every
other entries-table integration test in this suite -- it proves the
STORE reads/writes the right columns, not that the `cora_app` role
specifically can. The REVOKE (UPDATE/DELETE/TRUNCATE) is covered
generically by `tests/architecture/test_migration_revokes.py`'s static
regex scan, which needs no per-table case. The GRANT (SELECT/INSERT) is
NOT provable generically: `test_cora_app_role_revoke_postgres.py`'s own
docstring says a live INSERT against a `cora_app`-credentialed pool is
the only thing that proves Postgres actually honors a GRANT, migration
text is not enough. `entries_run_capture_probes` has its own entry in
that file's `_ENTRIES_TABLE_INSERTS` for exactly that reason.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.run.aggregates.run import CaptureProbe, PostgresCaptureProbeStore
from cora.shared.reach import ReachTier

_OBSERVED_AT = datetime(2026, 8, 14, 17, 19, 31, tzinfo=UTC)


def _probe(
    *,
    capture_code: str,
    source_id: str = "2bmb:TomoScan:ScanStatus",
    reach_tier: ReachTier = ReachTier.RELAYED,
    phase_claimed: bool = True,
    observed_at: datetime | None = _OBSERVED_AT,
) -> CaptureProbe:
    return CaptureProbe(
        event_id=uuid4(),
        capture_code=capture_code,
        source_kind="EpicsPv",
        source_id=source_id,
        reach_tier=reach_tier,
        phase_claimed=phase_claimed,
        observed_at=observed_at,
    )


@pytest.mark.integration
async def test_append_writes_a_row_readable_by_capture_code(db_pool: asyncpg.Pool) -> None:
    code = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    store = PostgresCaptureProbeStore(db_pool)
    probe = _probe(capture_code=code)

    await store.append([probe])

    row = await db_pool.fetchrow(
        "SELECT capture_code, source_kind, source_id, reach_tier, phase_claimed, observed_at "
        "FROM entries_run_capture_probes WHERE capture_code = $1",
        code,
    )
    assert row is not None
    assert row["source_kind"] == "EpicsPv"
    assert row["reach_tier"] == ReachTier.RELAYED.value
    assert row["phase_claimed"] is True
    assert row["observed_at"] == _OBSERVED_AT


@pytest.mark.integration
async def test_unreached_row_carries_a_null_observed_at(db_pool: asyncpg.Pool) -> None:
    code = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    store = PostgresCaptureProbeStore(db_pool)
    probe = _probe(
        capture_code=code,
        reach_tier=ReachTier.UNREACHED,
        phase_claimed=False,
        observed_at=None,
    )

    await store.append([probe])

    row = await db_pool.fetchrow(
        "SELECT reach_tier, phase_claimed, observed_at FROM entries_run_capture_probes "
        "WHERE capture_code = $1",
        code,
    )
    assert row is not None
    assert row["reach_tier"] == ReachTier.UNREACHED.value
    assert row["phase_claimed"] is False
    assert row["observed_at"] is None


@pytest.mark.integration
async def test_two_pvs_on_the_same_code_write_independent_rows(db_pool: asyncpg.Pool) -> None:
    """One row per (capture_code, PV), never collapsed per code -- see
    the module docstring's "per-PV, not per-code" argument."""
    code = f"2bmb-tomoscan-{uuid4().hex[:8]}"
    store = PostgresCaptureProbeStore(db_pool)
    status = _probe(capture_code=code, source_id="2bmb:TomoScan:ScanStatus")
    abort = _probe(capture_code=code, source_id="2bmb:TomoScan:AbortScan")

    await store.append([status, abort])

    rows = await db_pool.fetch(
        "SELECT source_id FROM entries_run_capture_probes WHERE capture_code = $1", code
    )
    assert {r["source_id"] for r in rows} == {"2bmb:TomoScan:ScanStatus", "2bmb:TomoScan:AbortScan"}
