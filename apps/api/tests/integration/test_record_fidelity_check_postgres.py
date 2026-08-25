"""The D6 record-fidelity operator command, end to end against a real
database and a real bundle written by `record_bundle_export`.

Four claims:

  - a Run refolded from the `full/` bundle folds to a state hash that
    matches the same Run loaded live from Postgres;
  - a bundle whose `full/` slot has been tampered with after export
    (simulating export or transport damage) is caught: `full/`
    reports a mismatch and the command's exit code says so;
  - the `published/` slot's tokenized identity makes a live comparison
    structurally impossible, and the command says exactly that rather
    than silently reporting zero matches as if it had tried and found
    none;
  - a bundle with no Run stream at all refuses cleanly.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.api.record_bundle_export import export_record_bundles
from cora.api.record_fidelity_check import (
    _EXIT_CLEAN,  # pyright: ignore[reportPrivateUsage]
    _EXIT_MISMATCH,  # pyright: ignore[reportPrivateUsage]
    _EXIT_REFUSED,  # pyright: ignore[reportPrivateUsage]
    check_record_fidelity,
)
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.postgres.pool import create_pool
from cora.run.aggregates.run import (
    ConductMode,
    RunCompleted,
    RunStarted,
    event_type_name,
    to_payload,
)
from tests._postgres import normalize_async_url

pytestmark = pytest.mark.integration

FidelityDatabase = tuple[asyncpg.Pool, str]

_NOW = datetime(2026, 8, 18, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest_asyncio.fixture
async def fidelity_database(
    postgres_container: PostgresContainer,
    template_database: str,
) -> AsyncGenerator[FidelityDatabase]:
    """A per-test database plus its URL: both `export_record_bundles`
    and `check_record_fidelity` build their own pool from a URL, mirroring
    `test_record_bundle_export_postgres.py`'s own fixture."""
    test_db = f"recfidelity_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool, test_url
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()


async def _seed_a_witnessed_run(pool: asyncpg.Pool) -> UUID:
    """One real Run stream, started and completed, appended directly
    through the event store (no handler ceremony needed for a fidelity
    check, which reads the stream back exactly as recorded)."""
    run_id = uuid4()
    started = RunStarted(
        run_id=run_id,
        name="2bmb commissioning scan",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
        conduct_mode=ConductMode.WITNESSED,
    )
    completed = RunCompleted(run_id=run_id, occurred_at=_NOW, observed_at=_NOW)

    store = PostgresEventStore(pool)
    for index, event in enumerate((started, completed)):
        new_event = to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=uuid4(),
            command_name="StartRun" if index == 0 else "CompleteRun",
            correlation_id=_CORRELATION_ID,
            principal_id=_PRINCIPAL_ID,
        )
        await store.append(
            stream_type="Run",
            stream_id=run_id,
            expected_version=index,
            events=[new_event],
        )
    return run_id


async def test_full_bundle_replays_and_matches_the_live_database(
    fidelity_database: FidelityDatabase, tmp_path: Path
) -> None:
    pool, url = fidelity_database
    await _seed_a_witnessed_run(pool)

    destination = tmp_path / "bundle"
    export_exit = await export_record_bundles(destination=destination, database_url=url)
    assert export_exit == _EXIT_CLEAN

    exit_code = await check_record_fidelity(bundle_root=destination, database_url=url)

    assert exit_code == _EXIT_CLEAN


async def test_full_bundle_reports_and_exits_on_a_tampered_row(
    fidelity_database: FidelityDatabase, tmp_path: Path
) -> None:
    """Simulates export/transport damage: after a clean export, one
    `full/streams.jsonl` row is hand-edited so the offline refold no
    longer agrees with what is still live in Postgres. This is the
    proof the check actually looks at content, not just that a bundle
    is present and well-formed."""
    pool, url = fidelity_database
    await _seed_a_witnessed_run(pool)

    destination = tmp_path / "bundle"
    export_exit = await export_record_bundles(destination=destination, database_url=url)
    assert export_exit == _EXIT_CLEAN

    streams_path = destination / "full" / "streams.jsonl"
    lines = streams_path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line]
    for row in rows:
        if row["event_type"] == "RunStarted":
            row["payload"]["name"] = "a name the live database never recorded"
    streams_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    exit_code = await check_record_fidelity(bundle_root=destination, database_url=url)

    assert exit_code == _EXIT_MISMATCH


async def test_published_bundle_never_reports_a_match_only_replayability(
    fidelity_database: FidelityDatabase, tmp_path: Path
) -> None:
    pool, url = fidelity_database
    await _seed_a_witnessed_run(pool)

    destination = tmp_path / "bundle"
    export_exit = await export_record_bundles(destination=destination, database_url=url)
    assert export_exit == _EXIT_CLEAN

    json_out = tmp_path / "fidelity.json"
    exit_code = await check_record_fidelity(
        bundle_root=destination, database_url=url, json_out=json_out
    )
    assert exit_code == _EXIT_CLEAN

    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["published_bundle"]["matched"] is None
    assert report["published_bundle"]["mismatched"] is None
    for row in report["published_bundle"]["rows"]:
        assert row["state_hash_recorded"] is None
        assert row["digests_match"] is None


async def test_refuses_cleanly_on_a_bundle_with_no_run_stream(
    fidelity_database: FidelityDatabase, tmp_path: Path
) -> None:
    """No Run was ever started: the exported bundle carries only
    bootstrap/seed events, so there is nothing D6 can check. Refuses
    rather than reporting a hollow `runs=0` success."""
    _pool, url = fidelity_database

    destination = tmp_path / "bundle"
    export_exit = await export_record_bundles(destination=destination, database_url=url)
    assert export_exit == _EXIT_CLEAN

    exit_code = await check_record_fidelity(bundle_root=destination, database_url=url)

    assert exit_code == _EXIT_REFUSED
