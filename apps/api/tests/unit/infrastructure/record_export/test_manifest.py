"""Unit tests for the export manifest.

`build_manifest` is pure (no I/O): every input is passed in, so these
tests construct synthetic `ExportedRecord`s directly rather than going
through a live database. The DB-backed acceptance path (via a real
Procedure + Run) lives in
`tests/integration/test_record_export_manifest_postgres.py`.
"""

import re

from cora.infrastructure.record_export import (
    ExportedRecord,
    build_manifest,
    capture_git_commit,
    hash_record,
    hash_redaction_profile,
)

_RUN_A = "01900000-0000-7000-8000-0000000000a1"
_RUN_B = "01900000-0000-7000-8000-0000000000a2"
_PROC_EXPANDED = "01900000-0000-7000-8000-0000000000b1"
_PROC_DIRECT = "01900000-0000-7000-8000-0000000000b2"
_PROC_NO_RUN = "01900000-0000-7000-8000-0000000000b3"


def _stream_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "stream_type": "Procedure",
        "stream_id": _PROC_EXPANDED,
        "event_type": "ProcedureStarted",
        "schema_version": 1,
        "payload": {},
    }
    row.update(overrides)
    return row


def _procedure_registered(
    procedure_id: str, parent_run_id: str | None, *, schema_version: int = 1
) -> dict[str, object]:
    return _stream_row(
        stream_id=procedure_id,
        event_type="ProcedureRegistered",
        schema_version=schema_version,
        payload={"procedure_id": procedure_id, "parent_run_id": parent_run_id},
    )


def _recipe_expansion_recorded(procedure_id: str) -> dict[str, object]:
    return _stream_row(
        stream_id=procedure_id,
        event_type="RecipeExpansionRecorded",
        payload={"procedure_id": procedure_id},
    )


def _run_started(run_id: str) -> dict[str, object]:
    return _stream_row(stream_type="Run", stream_id=run_id, event_type="RunStarted", payload={})


def _record() -> ExportedRecord:
    streams = (
        _run_started(_RUN_A),
        _run_started(_RUN_B),
        _procedure_registered(_PROC_EXPANDED, _RUN_A),
        _recipe_expansion_recorded(_PROC_EXPANDED),
        _procedure_registered(_PROC_DIRECT, _RUN_B),
        _procedure_registered(_PROC_NO_RUN, None),
        _procedure_registered("01900000-0000-7000-8000-0000000000b9", None, schema_version=2),
    )
    logbooks: dict[str, tuple[dict[str, object], ...]] = {
        "activity": ({"step_kind": "setpoint"}, {"step_kind": "check"}),
        "observation": ({"is_simulated": True}, {"is_simulated": True}),
    }
    return ExportedRecord(streams=streams, logbooks=logbooks)


def test_logbook_row_counts_match_each_kinds_length() -> None:
    manifest = build_manifest(_record(), watermark=100, git_commit="deadbeef")
    assert manifest.row_count_by_logbook_kind == {"activity": 2, "observation": 2}


def test_max_schema_version_takes_the_max_per_event_type() -> None:
    manifest = build_manifest(_record(), watermark=100, git_commit="deadbeef")
    # Two ProcedureRegistered rows in the fixture: schema_version 1 (the
    # three _procedure_registered() calls) and 2 (the last row).
    assert manifest.max_schema_version_by_event_type["ProcedureRegistered"] == 2
    assert manifest.max_schema_version_by_event_type["RunStarted"] == 1


def test_is_simulated_true_when_every_observation_says_so() -> None:
    manifest = build_manifest(_record(), watermark=100, git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_is_simulated_false_on_a_single_dissenting_observation() -> None:
    record = ExportedRecord(
        streams=(),
        logbooks={"observation": ({"is_simulated": True}, {"is_simulated": False})},
    )
    manifest = build_manifest(record, watermark=100, git_commit="deadbeef")
    assert manifest.is_simulated is False


def test_is_simulated_vacuously_true_with_no_observations() -> None:
    record = ExportedRecord(streams=(), logbooks={})
    manifest = build_manifest(record, watermark=100, git_commit="deadbeef")
    assert manifest.is_simulated is True


def test_expansion_digest_present_only_for_the_run_whose_child_was_expanded() -> None:
    manifest = build_manifest(_record(), watermark=100, git_commit="deadbeef")
    assert manifest.expansion_digest_presence_by_run == {_RUN_A: True, _RUN_B: False}


def test_expansion_digest_ignores_procedures_with_no_parent_run() -> None:
    """_PROC_NO_RUN has parent_run_id=None; it must not create a phantom
    run entry or affect either real run's result."""
    manifest = build_manifest(_record(), watermark=100, git_commit="deadbeef")
    assert set(manifest.expansion_digest_presence_by_run) == {_RUN_A, _RUN_B}


def test_manifest_hashes_match_calling_the_hash_functions_directly() -> None:
    record = _record()
    manifest = build_manifest(record, watermark=100, git_commit="deadbeef")
    assert manifest.record_hash == hash_record(record)
    assert manifest.redaction_profile_hash == hash_redaction_profile()


def test_manifest_carries_the_watermark_and_commit_verbatim() -> None:
    manifest = build_manifest(_record(), watermark=4242, git_commit="cafef00d")
    assert manifest.watermark == 4242
    assert manifest.git_commit == "cafef00d"


def test_capture_git_commit_returns_a_full_sha() -> None:
    commit = capture_git_commit()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)


def test_unfired_tier2_clearances_absent_without_redaction() -> None:
    """`None` means no redaction happened, the same convention as
    `published_record_hash`; unrelated to whether any clearance would
    have fired."""
    manifest = build_manifest(_record(), watermark=1, git_commit="deadbeef")
    assert manifest.unfired_tier2_clearances is None


def test_unfired_tier2_clearances_empty_when_none_supplied_but_redacted() -> None:
    """Passing `redacted` without `unfired_tier2_clearances` reports an
    empty tuple, not `None`: redaction DID happen, so absence-as-signal
    no longer applies, and "empty" correctly reads as "nothing to
    report" rather than "not tracked"."""
    record = _record()
    manifest = build_manifest(record, watermark=1, git_commit="deadbeef", redacted=record)
    assert manifest.unfired_tier2_clearances == ()


def test_unfired_tier2_clearances_renders_sorted_kind_column_pointer() -> None:
    record = _record()
    manifest = build_manifest(
        record,
        watermark=1,
        git_commit="deadbeef",
        redacted=record,
        unfired_tier2_clearances=frozenset(
            {
                ("activity", "payload", "units"),
                ("activity", "payload", "channel"),
            }
        ),
    )
    assert manifest.unfired_tier2_clearances == (
        "activity/payload/channel",
        "activity/payload/units",
    )
