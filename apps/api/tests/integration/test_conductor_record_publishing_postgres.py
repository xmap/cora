"""End-to-end: a real Conductor run, published, and read back honest.

Slice 6 of project_record_publishing_campaign.md's deliverable 4. Every
other end-to-end record-export test
(`test_record_export_bundle_postgres.py`) seeds `entries_operation_procedure_activities`
rows by hand with a route-shaped payload that never matched what the
Conductor actually writes -- that mismatch is exactly what let
`TIER2_JSONB_CLEARED_POINTERS[("activity", "payload")]` clear three
keys (`channel`, `action_name`, `units`) the real code never wrote. This
test closes that gap by splicing the two already-proven halves that
were never run back to back:

- the CONDUCTING half, reused near-verbatim from
  `test_conductor_against_softioc_postgres.py`: a real `Conductor`
  driving `EpicsCaControlPort` against the shared softIOC subprocess and
  a real `PostgresActivityStore`.
- the EXPORT/REDACT/BUNDLE/VERIFY half, reused near-verbatim from
  `test_record_export_bundle_postgres.py`: `export_record` ->
  `redact_record` -> `build_manifest` -> `write_bundle`, verified by the
  standalone `scripts/verify_record_hash.py` in a subprocess that never
  imports `cora` (the isolation is structural -- the script simply never
  does `import cora` -- not an explicit `PYTHONPATH` strip, matching
  every other test that shells out to it).

The point of this test is the CONTENT assertion, not merely that the
bundle verifies (every other test here already proves that): a
published record of a real conducted run must be able to say what
address was set, what was checked, what was read, and whether the step
passed. Before slice 6 none of that survived redaction.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import (
    build_manifest,
    capture_git_commit,
    capture_source_row_count_by_logbook_kind,
    export_record,
    hash_redaction_profile,
    redact_record,
    write_bundle,
)
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.aggregates.procedure import (
    PostgresActivityStore,
    ProcedureRegistered,
    event_type_name,
    to_payload,
)
from cora.operation.conductor import CheckStep, Conductor, SetpointStep, WithinToleranceCriterion
from cora.operation.features.abort_procedure import bind as bind_abort
from cora.operation.features.append_activities import bind as bind_append
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.start_procedure import bind as bind_start
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000030d0099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000030d00aa")
_REPO_ROOT = Path(__file__).resolve().parents[4]
_VERIFIER = _REPO_ROOT / "scripts" / "verify_record_hash.py"


def _control_port(softioc: str) -> ControlPortRegistry:
    """Same wiring as `test_conductor_against_softioc_postgres.py`'s
    helper of the same name: the Conductor takes the registry, not the
    bare substrate adapter."""
    registry = ControlPortRegistry()
    registry.register_substrate_port(softioc, EpicsCaControlPort(), "epics_ca")
    return registry


async def _seed_defined_procedure(deps_event_store: object, procedure_id: UUID) -> None:
    """Seed a single ProcedureRegistered event so the Procedure exists in
    `Defined`, bypassing `register_procedure`'s cross-aggregate
    validation the same way the softIOC test does."""
    registered = ProcedureRegistered(
        procedure_id=procedure_id,
        name="2-BM bakeout, published",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )
    stored = to_new_event(
        event_type=event_type_name(registered),
        payload=to_payload(registered),
        occurred_at=registered.occurred_at,
        event_id=UUID("01900000-0000-7000-8000-0000030d0001"),
        command_name="RegisterProcedure",
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
    )
    await deps_event_store.append(  # type: ignore[attr-defined]
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[stored],
    )


def _verify(bundle: Path, *, published: bool = False) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(_VERIFIER), "verify-bundle", str(bundle)]
    if published:
        argv.append("--published")
    return subprocess.run(argv, capture_output=True, text=True)


def _activity_rows(bundle: Path) -> list[dict[str, Any]]:
    path = bundle / "logbooks" / "activity.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.integration
async def test_a_real_conducted_run_publishes_what_it_did(
    db_pool: asyncpg.Pool, softioc: str, tmp_path: Path
) -> None:
    procedure_id = UUID("01900000-0000-7000-8000-0000030d0100")
    logbook_id = UUID("01900000-0000-7000-8000-0000030d0101")
    open_event_id = UUID("01900000-0000-7000-8000-0000030d0102")
    started_event_id = UUID("01900000-0000-7000-8000-0000030d0103")
    setpoint_marker_id = UUID("01900000-0000-7000-8000-0000030d0104")
    setpoint_outcome_id = UUID("01900000-0000-7000-8000-0000030d0105")
    check_step_id = UUID("01900000-0000-7000-8000-0000030d0106")
    completed_event_id = UUID("01900000-0000-7000-8000-0000030d0107")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            setpoint_marker_id,
            setpoint_outcome_id,
            check_step_id,
            completed_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = _control_port(softioc)
    conductor = Conductor(
        control_port=control_port,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )

    address = f"{softioc}double_value"
    try:
        await control_port.write(address, 42.0, wait=True)
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                SetpointStep(address=address, value=7.5, verify=True),
                CheckStep(
                    address=address,
                    criterion=WithinToleranceCriterion(expected=7.5, tolerance=0.01),
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is True

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)
        source_row_count_by_logbook_kind = await capture_source_row_count_by_logbook_kind(pg_conn)

    redaction = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    manifest = build_manifest(
        exported,
        git_commit=capture_git_commit(),
        source_row_count_by_logbook_kind=source_row_count_by_logbook_kind,
        redaction=redaction,
    )
    bundle = write_bundle(redaction.redacted_record, manifest, tmp_path / "published")

    verified = _verify(bundle, published=True)
    assert verified.returncode == 0, verified.stderr

    rows = _activity_rows(bundle)
    by_result: dict[tuple[str, str], dict[str, Any]] = {
        (row["step_kind"], row["payload"]["result"]): row["payload"] for row in rows
    }

    setpoint_ok = by_result[("setpoint", "ok")]
    assert setpoint_ok["address"] == address
    assert setpoint_ok["result"] == "ok"
    assert setpoint_ok["post_reading"]["value"] == 7.5
    assert setpoint_ok["post_reading"]["kind"] is not None
    assert setpoint_ok["post_reading"]["quality"] == "Good"
    # Not cleared: a full-precision substrate timestamp drops even when
    # its parent object is published (feedback-claims-need-a-threat-model).
    assert "sampled_at" not in setpoint_ok["post_reading"]

    check_ok = by_result[("check", "ok")]
    assert check_ok["address"] == address
    assert check_ok["result"] == "ok"
    assert check_ok["criterion"] == {
        "kind": "within_tolerance",
        "expected": 7.5,
        "tolerance": 0.01,
    }
    assert check_ok["reading"]["value"] == 7.5
    assert check_ok["reading"]["quality"] == "Good"
    assert "sampled_at" not in check_ok["reading"]


@pytest.mark.integration
async def test_a_failed_check_publishes_the_failure_without_leaking_the_message(
    db_pool: asyncpg.Pool, softioc: str, tmp_path: Path
) -> None:
    """The happy-path test above proves cleared fields survive; this
    proves the deliberately-uncleared ones actually drop on a REAL
    conducted failure, not just in the unit-level fixtures in
    `test_redact_tier2.py`. A criterion mismatch is the cheapest real
    failure to provoke: no port-level error injection needed, just an
    `expected` the softIOC's actual value won't satisfy.
    """
    procedure_id = UUID("01900000-0000-7000-8000-0000030d0200")
    logbook_id = UUID("01900000-0000-7000-8000-0000030d0201")
    open_event_id = UUID("01900000-0000-7000-8000-0000030d0202")
    started_event_id = UUID("01900000-0000-7000-8000-0000030d0203")
    setpoint_marker_id = UUID("01900000-0000-7000-8000-0000030d0204")
    setpoint_outcome_id = UUID("01900000-0000-7000-8000-0000030d0205")
    check_step_id = UUID("01900000-0000-7000-8000-0000030d0206")
    aborted_event_id = UUID("01900000-0000-7000-8000-0000030d0207")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            started_event_id,
            logbook_id,
            open_event_id,
            setpoint_marker_id,
            setpoint_outcome_id,
            check_step_id,
            aborted_event_id,
        ],
    )
    await _seed_defined_procedure(deps.event_store, procedure_id)
    step_store = PostgresActivityStore(db_pool)
    control_port = _control_port(softioc)
    conductor = Conductor(
        control_port=control_port,
        append_step=bind_append(deps, step_store=step_store),
        clock=deps.clock,
        id_generator=deps.id_generator,
        start_procedure=bind_start(deps),
        complete_procedure=bind_complete(deps),
        abort_procedure=bind_abort(deps),
    )

    address = f"{softioc}double_value"
    try:
        await control_port.write(address, 7.5, wait=True)
        result = await conductor.conduct(
            procedure_id=procedure_id,
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
            steps=(
                SetpointStep(address=address, value=7.5),
                CheckStep(
                    address=address,
                    criterion=WithinToleranceCriterion(expected=999.0, tolerance=0.01),
                ),
            ),
        )
    finally:
        await control_port.aclose()

    assert result.succeeded is False

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)
        source_row_count_by_logbook_kind = await capture_source_row_count_by_logbook_kind(pg_conn)

    redaction = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    manifest = build_manifest(
        exported,
        git_commit=capture_git_commit(),
        source_row_count_by_logbook_kind=source_row_count_by_logbook_kind,
        redaction=redaction,
    )
    bundle = write_bundle(redaction.redacted_record, manifest, tmp_path / "published")

    verified = _verify(bundle, published=True)
    assert verified.returncode == 0, verified.stderr

    rows = _activity_rows(bundle)
    by_result: dict[tuple[str, str], dict[str, Any]] = {
        (row["step_kind"], row["payload"]["result"]): row["payload"] for row in rows
    }

    check_failed = by_result[("check", "failed")]
    assert check_failed["address"] == address
    assert check_failed["result"] == "failed"
    assert check_failed["error_class"] == "CheckFailedError"
    assert check_failed["criterion"] == {
        "kind": "within_tolerance",
        "expected": 999.0,
        "tolerance": 0.01,
    }
    assert check_failed["reading"]["value"] == 7.5
    assert check_failed["reading"]["quality"] == "Good"
    # The core negative-path proof: conductor.py's `message=str(exc)` for
    # this failure includes the mismatch reason as free text, and it must
    # not survive redaction even though its sibling `error_class` does.
    assert "message" not in check_failed
