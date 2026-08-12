"""Acceptance test for Step 6 of the record exporter build brief.

Per `project_record_export_build_brief.md` step 6: a bare `str` on a NEW
event drops with nobody editing a list; an event type absent from the
disposition table aborts; no raw store identifier survives the export
(NOT "no join key" -- timestamps remain one, deliberately); a rehearsal
export contains no real principal, ASSERTED rather than assumed.

Built the same way steps 2-4's acceptance tests were: a real Procedure
through Running with a real activity appended, via the real handlers,
then `export_record` + `redact_record` against the live database.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.record_export import (
    RedactionProfileMismatchError,
    UnknownEventTypeError,
    export_record,
    hash_redaction_profile,
    redact_record,
)
from cora.infrastructure.record_export._redact_tier2 import TIER2_DISPOSITIONS
from cora.infrastructure.record_export._registry import all_specs
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


def _collect_string_leaves(value: object, out: set[str]) -> None:
    if isinstance(value, dict):
        for sub in value.values():
            _collect_string_leaves(sub, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_string_leaves(item, out)
    elif isinstance(value, str):
        out.add(value)


async def _seed_running_procedure_with_activity(db_pool: asyncpg.Pool, procedure_id: UUID) -> None:
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

    # A single setpoint-only activity would leave the activity kind's
    # `action_name` and `units` clearances unfired: a real whole-database
    # export accumulates many activities across many procedures over
    # time and would plausibly exercise every step kind, so this mirrors
    # that with one of each (same 3-entry shape as step 2's fixture)
    # rather than under-representing a real export.
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


@pytest.mark.integration
async def test_bare_str_field_drops_and_no_real_principal_survives(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    result = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    redacted = result.redacted_record

    registered_rows = [
        row for row in redacted.streams if row["event_type"] == "ProcedureRegistered"
    ]
    assert len(registered_rows) == 1
    registered_payload = registered_rows[0]["payload"]
    assert isinstance(registered_payload, dict)
    # ProcedureRegistered.name and .kind are drop:text in the real,
    # generated table -- no test-only disposition edited for this.
    assert "name" not in registered_payload
    assert "kind" not in registered_payload

    # ASSERTED, not assumed: the real principal/actor UUID used to build
    # this fixture must not appear anywhere in the redacted output.
    leaves: set[str] = set()
    for row in redacted.streams:
        _collect_string_leaves(row, leaves)
    for rows in redacted.logbooks.values():
        for row in rows:
            _collect_string_leaves(row, leaves)
    assert str(_PRINCIPAL_ID) not in leaves
    assert str(procedure_id) not in leaves
    assert str(_CORRELATION_ID) not in leaves


@pytest.mark.integration
async def test_event_type_absent_from_disposition_table_aborts(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    tampered_streams = list(exported.streams)
    tampered_streams[0] = {**tampered_streams[0], "event_type": "ThisEventTypeDoesNotExist"}
    tampered = dataclasses.replace(exported, streams=tuple(tampered_streams))

    with pytest.raises(UnknownEventTypeError) as excinfo:
        redact_record(tampered, expected_redaction_profile_hash=hash_redaction_profile())
    assert excinfo.value.event_type == "ThisEventTypeDoesNotExist"


@pytest.mark.integration
async def test_no_raw_uuid_survives_the_redacted_export(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    raw_uuids: set[str] = set()
    for row in exported.streams:
        for key in ("event_id", "stream_id", "correlation_id", "causation_id", "principal_id"):
            value = row.get(key)
            if isinstance(value, str):
                raw_uuids.add(value)
    for rows in exported.logbooks.values():
        for row in rows:
            for value in row.values():
                if isinstance(value, str) and len(value) == 36 and value.count("-") == 4:
                    raw_uuids.add(value)

    result = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())

    redacted_leaves: set[str] = set()
    for row in result.redacted_record.streams:
        _collect_string_leaves(row, redacted_leaves)
    for rows in result.redacted_record.logbooks.values():
        for row in rows:
            _collect_string_leaves(row, redacted_leaves)

    assert raw_uuids, "fixture produced no UUIDs to check -- test would pass vacuously"
    assert raw_uuids.isdisjoint(redacted_leaves)


@pytest.mark.integration
async def test_wrong_redaction_profile_hash_refuses_before_redacting(db_pool: asyncpg.Pool) -> None:
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    with pytest.raises(RedactionProfileMismatchError):
        redact_record(exported, expected_redaction_profile_hash="0" * 64)


@pytest.mark.integration
async def test_unfired_tier1_fields_is_empty_for_a_realistic_export(db_pool: asyncpg.Pool) -> None:
    """A real export naturally exercises every declared field of every
    event type it carries: a stored payload includes a key, even as
    `null`, on any `schema_version` that still declares it. The tier-1
    completeness twin to tier-2's `unfired_tier2_clearances` should be
    empty for a normal fixture, not merely small."""
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    result = redact_record(exported, expected_redaction_profile_hash=hash_redaction_profile())
    assert result.unfired_tier1_fields == frozenset()


@pytest.mark.integration
async def test_unfired_tier1_fields_names_a_declared_field_missing_from_every_row_of_its_type(
    db_pool: asyncpg.Pool,
) -> None:
    """Simulates an older `schema_version` row: a declared field
    (`ProcedureRegistered.kind`, a real `DISPOSITIONS` key) removed from
    the only `ProcedureRegistered` row this export carries must be
    reported as unfired for that event type -- the narrowness caveat a
    build-time guard cannot see, because the field is not missing from
    the TABLE, only from every row THIS export happens to carry."""
    procedure_id = uuid4()
    await _seed_running_procedure_with_activity(db_pool, procedure_id)

    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        exported = await export_record(pg_conn)

    streams = list(exported.streams)
    for index, row in enumerate(streams):
        if row["event_type"] == "ProcedureRegistered":
            raw_payload = row["payload"]
            assert isinstance(raw_payload, dict)
            payload = dict(raw_payload)
            del payload["kind"]
            streams[index] = {**row, "payload": payload}
    tampered = dataclasses.replace(exported, streams=tuple(streams))

    result = redact_record(tampered, expected_redaction_profile_hash=hash_redaction_profile())
    assert ("ProcedureRegistered", "kind") in result.unfired_tier1_fields


@pytest.mark.integration
@pytest.mark.parametrize("spec", all_specs(), ids=lambda spec: spec.kind)
async def test_tier2_disposition_table_columns_match_live_schema(
    db_pool: asyncpg.Pool, spec: object
) -> None:
    """Drift guard: TIER2_DISPOSITIONS[kind] must enumerate every column
    the live table actually has, nothing more, nothing less -- a new
    migration adding a column must fail this test until this file is
    updated, the same posture step 1's registry completeness test takes
    for the registry itself."""
    async with db_pool.acquire() as conn:
        pg_conn: asyncpg.Connection = conn  # type: ignore[assignment]
        rows = await pg_conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
            spec.table,  # type: ignore[attr-defined]
        )
    live_columns = {row["column_name"] for row in rows}
    declared_columns = set(TIER2_DISPOSITIONS[spec.kind].keys())  # type: ignore[attr-defined]
    assert declared_columns == live_columns, (
        f"kind={spec.kind!r}: TIER2_DISPOSITIONS declares {declared_columns} but "  # type: ignore[attr-defined]
        f"{spec.table!r} actually has {live_columns}"  # type: ignore[attr-defined]
    )
