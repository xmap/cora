"""The Definition of Done, end to end, against a real database.

`project_record_export_build_brief.md`: "A rehearsal scenario runs, the
exporter writes a bundle, the standalone verifier passes on it in a
subprocess with no cora on the path."

Every stage of that sentence is a separate already-tested unit. This is
the one test that runs them in sequence against live Postgres, because
the failure this catches is the seam: a row shape that only a real
export produces, serialized to JSONL, reassembled by a reimplementation
that shares no code with the writer, and hashed to the same value. Any
drift between the two reassembly implementations shows up here and
nowhere else.

FOUND WHILE WRITING THIS, and not fixed here because loosening a
fail-closed check is a security decision rather than a test fixture's
business: `ensure_all_clearances_fired` raises unless EVERY declared
`activity/payload` clearance fires, and those three keys (`channel`,
`action_name`, `units`) live on different step kinds, two of them
optional per `append_activities/route.py:86-94`. So `redact_record`
refuses on any export whose activities happen not to include a
setpoint-carrying-units AND an action AND a check. Step 6's own
integration fixture already works around it with a comment reasoning
that a whole-database export "would plausibly exercise every step
kind". That is an assumption about data, holding up a hard refusal. It
fails CLOSED, so nothing leaks, but the first small rehearsal bundle,
or any future per-run slice, would hit it and read as a config error.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import (
    MANIFEST_NAME,
    RECORD_PAYLOAD_TYPE,
    STREAMS_NAME,
    build_manifest,
    capture_git_commit,
    export_record,
    hash_redaction_profile,
    read_bundle_body,
    redact_record,
    write_bundle,
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
_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERIFIER = _REPO_ROOT / "scripts" / "verify_record_hash.py"


async def _seed_a_procedure_with_one_activity(db_pool: asyncpg.Pool) -> None:
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

    # Three step kinds, not one, and NOT because this test needs three.
    # `ensure_all_clearances_fired` raises unless every declared
    # `activity/payload` clearance (`channel`, `action_name`, `units`)
    # matches at least one row, and those keys live on DIFFERENT step
    # kinds, two of them optional. A setpoint-only export therefore
    # fails to redact. See this module's docstring: that is a real
    # fragility in step 6, worked around here so these tests exercise
    # the BUNDLE rather than accidentally re-testing the clearance rule.
    handler = bind_append(deps, step_store=PostgresActivityStore(db_pool))
    await handler(
        AppendProcedureActivities(
            procedure_id=procedure_id,
            entries=(
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="setpoint",
                    payload={"channel": "T_oven", "target_value": 423.0, "units": "K"},
                    sampled_at=_NOW,
                ),
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="action",
                    payload={"action_name": "open_valve", "params": {"valve": "V12"}},
                    sampled_at=_NOW,
                ),
                ActivityInput(
                    event_id=uuid4(),
                    step_kind="check",
                    payload={"channel": "T_oven", "passed": True},
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


def _verify_body(body_file: Path, expected: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_VERIFIER),
            "verify",
            "--payload-type",
            RECORD_PAYLOAD_TYPE,
            "--expected-hash",
            expected,
            str(body_file),
        ],
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
async def test_a_real_export_writes_a_bundle_a_stranger_can_verify(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    await _seed_a_procedure_with_one_activity(db_pool)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    manifest = build_manifest(exported, watermark=1, git_commit=capture_git_commit())
    bundle = write_bundle(exported, manifest, tmp_path / "bundle")

    assert (bundle / STREAMS_NAME).is_file()
    assert (bundle / MANIFEST_NAME).is_file()
    assert (bundle / "logbooks" / "activity.jsonl").is_file()

    result = _verify(bundle)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


@pytest.mark.integration
async def test_a_real_redacted_export_verifies_against_h3(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    await _seed_a_procedure_with_one_activity(db_pool)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    redaction = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    manifest = build_manifest(
        exported,
        watermark=1,
        git_commit=capture_git_commit(),
        redacted=redaction.redacted_record,
    )
    bundle = write_bundle(redaction.redacted_record, manifest, tmp_path / "published")

    result = _verify(bundle, published=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
async def test_a_real_bundle_fails_verification_after_one_edited_digit(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """The seal is only worth what its sensitivity is worth."""
    await _seed_a_procedure_with_one_activity(db_pool)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    manifest = build_manifest(exported, watermark=1, git_commit=capture_git_commit())
    bundle = write_bundle(exported, manifest, tmp_path / "bundle")
    assert _verify(bundle).returncode == 0

    path = bundle / "logbooks" / "activity.jsonl"
    tampered = path.read_text(encoding="utf-8").replace("423.0", "424.0")
    path.write_text(tampered, encoding="utf-8")

    after = _verify(bundle)
    assert after.returncode == 1
    assert "MISMATCH" in after.stderr


@pytest.mark.integration
async def test_both_reassembly_implementations_agree_on_a_real_bundle(
    db_pool: asyncpg.Pool, tmp_path: Path
) -> None:
    """CORA's reader and the standalone script's reader are separate code
    by design (F4). This pins them to the same answer on a real export,
    which is the only place their drift would be caught."""
    await _seed_a_procedure_with_one_activity(db_pool)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    manifest = build_manifest(exported, watermark=1, git_commit=capture_git_commit())
    bundle = write_bundle(exported, manifest, tmp_path / "bundle")

    # CORA's reader reassembles the body; the script's reader then has to
    # agree, twice over: once by hashing CORA's reassembly to the
    # manifest value (below) and once by reassembling the bundle itself
    # (`verify-bundle`, the tests above). Both paths must land on the
    # same digest or the two implementations have drifted.
    body_file = tmp_path / "body.json"
    body_file.write_text(json.dumps(read_bundle_body(bundle)), encoding="utf-8")
    result = _verify_body(body_file, manifest.record_hash)
    assert result.returncode == 0, result.stderr
