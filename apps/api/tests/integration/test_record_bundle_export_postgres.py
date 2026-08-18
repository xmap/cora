"""The S5d operator command, end to end against a real database.

`export_record_bundles` opens its own `REPEATABLE READ` transaction and
its own pool from a URL (mirroring `pilot_seed`'s own ceremony
function), so this suite builds a dedicated per-test database plus its
URL, the same shape `test_pilot_seed_postgres.py`'s `seed_database`
fixture uses, rather than borrowing the shared `db_pool` fixture's pool.

Four claims:

  - a populated database exports BOTH bundles from one snapshot, and
    the standalone verifier passes on each, in its own subprocess with
    no `cora` on the path;
  - the published bundle actually differs from the full one on a field
    tier 1 tokenizes, so "published" is proved, not merely asserted;
  - writing into an already-occupied `full/` or `published/` refuses
    cleanly, with the documented exit code, before either bundle is
    written;
  - an empty database refuses cleanly rather than writing a bundle
    claiming to be a record with nothing in it.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.api.record_bundle_export import (
    _EXIT_CLEAN,  # pyright: ignore[reportPrivateUsage]
    _EXIT_REFUSED,  # pyright: ignore[reportPrivateUsage]
    export_record_bundles,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.record_export import LogbookKindRowCountMismatchError
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
from tests._postgres import normalize_async_url
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.integration

ExportDatabase = tuple[asyncpg.Pool, str]

_NOW = datetime(2026, 8, 18, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERIFIER = _REPO_ROOT / "scripts" / "verify_record_hash.py"


@pytest_asyncio.fixture
async def export_database(
    postgres_container: PostgresContainer,
    template_database: str,
) -> AsyncGenerator[ExportDatabase]:
    """A per-test database plus its URL, because the command builds its
    own pool from a URL rather than borrowing the fixture's."""
    test_db = f"recbundle_{uuid4().hex[:12]}"
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


async def _seed_a_procedure_with_one_activity(pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    logbook_id = uuid4()
    open_event_id = uuid4()
    deps = build_postgres_deps(pool, now=_NOW, ids=[logbook_id, open_event_id])

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

    handler = bind_append(deps, step_store=PostgresActivityStore(pool))
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="setpoint",
                    payload={"address": "T_oven", "value": 423.0},
                    sampled_at=_NOW,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


def _verify(bundle: Path, *, published: bool = False) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(_VERIFIER), "verify-bundle", str(bundle)]
    if published:
        argv.append("--published")
    return subprocess.run(argv, capture_output=True, text=True)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def test_export_writes_full_and_published_bundles_that_both_verify(
    export_database: ExportDatabase, tmp_path: Path
) -> None:
    pool, url = export_database
    await _seed_a_procedure_with_one_activity(pool)

    destination = tmp_path / "bundle"
    exit_code = await export_record_bundles(destination=destination, database_url=url)
    assert exit_code == _EXIT_CLEAN

    full = destination / "full"
    published = destination / "published"
    for bundle in (full, published):
        assert (bundle / "manifest.json").is_file()
        assert (bundle / "streams.jsonl").is_file()
        assert (bundle / "logbooks" / "activity.jsonl").is_file()

    full_manifest = json.loads((full / "manifest.json").read_text(encoding="utf-8"))
    published_manifest = json.loads((published / "manifest.json").read_text(encoding="utf-8"))
    assert full_manifest["published_record_hash"] is None
    assert isinstance(published_manifest["published_record_hash"], str)

    full_result = _verify(full)
    assert full_result.returncode == 0, full_result.stderr
    published_result = _verify(published, published=True)
    assert published_result.returncode == 0, published_result.stderr


async def test_published_bundle_differs_from_full_on_a_tokenized_field(
    export_database: ExportDatabase, tmp_path: Path
) -> None:
    """`stream_id` is one of `_redact_tier1.FIXED_TOKEN_COLUMNS`: the
    published bundle must carry a per-export surrogate for it, never the
    real value the full bundle carries, proving the published bundle is
    an actual redaction rather than a second unredacted copy."""
    pool, url = export_database
    await _seed_a_procedure_with_one_activity(pool)

    destination = tmp_path / "bundle"
    exit_code = await export_record_bundles(destination=destination, database_url=url)
    assert exit_code == _EXIT_CLEAN

    full_streams = _read_jsonl(destination / "full" / "streams.jsonl")
    published_streams = _read_jsonl(destination / "published" / "streams.jsonl")

    assert len(full_streams) == len(published_streams)
    assert len(full_streams) > 0
    for full_row, published_row in zip(full_streams, published_streams, strict=True):
        assert full_row["event_type"] == published_row["event_type"]
        assert full_row["stream_id"] != published_row["stream_id"], (
            "the published bundle's stream_id must be a tokenized surrogate, "
            "never the real value the full bundle carries"
        )


async def test_refuses_when_full_destination_already_occupied(
    export_database: ExportDatabase, tmp_path: Path
) -> None:
    pool, url = export_database
    await _seed_a_procedure_with_one_activity(pool)

    destination = tmp_path / "bundle"
    full_dir = destination / "full"
    full_dir.mkdir(parents=True)
    (full_dir / "leftover_from_a_prior_export.json").write_text("{}", encoding="utf-8")

    exit_code = await export_record_bundles(destination=destination, database_url=url)
    assert exit_code == _EXIT_REFUSED

    # The refusal fires before either bundle is written: `published/`
    # is checked second and must never even be created, and the
    # occupied `full/` slot must be untouched beyond the stray file.
    assert not (destination / "published").exists()
    assert [p.name for p in full_dir.iterdir()] == ["leftover_from_a_prior_export.json"]


async def test_returns_the_refusal_exit_code_on_an_empty_database(
    export_database: ExportDatabase, tmp_path: Path
) -> None:
    """The migrated template already carries its own bootstrap events
    (this database's watermark is never zero straight off the
    template), so "empty" is forced here by truncating `events`
    directly rather than relied on as the template's own starting
    state."""
    pool, url = export_database
    await pool.execute("TRUNCATE TABLE events")

    destination = tmp_path / "bundle"
    exit_code = await export_record_bundles(destination=destination, database_url=url)
    assert exit_code == _EXIT_REFUSED
    assert not (destination / "full" / "manifest.json").exists()
    assert not (destination / "published" / "manifest.json").exists()


async def test_row_count_mismatch_propagates_rather_than_a_clean_refusal(
    export_database: ExportDatabase, tmp_path: Path
) -> None:
    """The S2b hard-error path through the REAL operator command, not just
    `_shell.export_bundle` (covered in
    `test_record_export_row_count_independence_postgres.py`): an orphan
    `activity` row -- written directly through `PostgresActivityStore`
    with a `logbook_id` no envelope ever names, the same technique as that
    sibling test -- must make `export_record_bundles` raise
    `LogbookKindRowCountMismatchError`, never return `_EXIT_REFUSED`. A
    unit-level pin that the error stays out of `_REFUSAL_ERRORS` lives in
    `tests/unit/api/test_record_bundle_export.py`; this is the end-to-end
    proof that nothing between here and there ends up softening it, and
    that no bundle lands on disk either way."""
    pool, url = export_database
    await _seed_a_procedure_with_one_activity(pool)
    await PostgresActivityStore(pool).append(
        [
            Activity(
                event_id=uuid4(),
                procedure_id=uuid4(),
                logbook_id=uuid4(),
                actor_id=uuid4(),
                command_name="AppendProcedureActivities",
                step_kind="setpoint",
                payload={"address": "T_orphan", "value": 1.0},
                sampled_at=_NOW,
                occurred_at=_NOW,
                correlation_id=uuid4(),
                causation_id=None,
            )
        ]
    )

    destination = tmp_path / "bundle"
    with pytest.raises(LogbookKindRowCountMismatchError) as excinfo:
        await export_record_bundles(destination=destination, database_url=url)

    assert excinfo.value.kind == "activity"
    assert excinfo.value.source_row_count == 2
    assert excinfo.value.exported_row_count == 1
    # _refuse_if_occupied pre-creates both directories (to check they're
    # empty) even on this path, same as the empty-database refusal test
    # above -- the property that matters is no manifest, meaning no
    # complete-looking bundle, ever lands.
    assert not (destination / "full" / "manifest.json").exists()
    assert not (destination / "published" / "manifest.json").exists()
