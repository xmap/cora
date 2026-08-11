"""Unit tests for hashing an exported record.

Per `project_record_export_v3.md` F2: no exclusions, stable across
re-exports of the same content, sensitive to any single differing byte.
These tests exercise that purely as a function of Python data (no DB
needed); the DB-backed "same database exported twice" acceptance test
lives in `tests/integration/test_record_export_hashing_postgres.py`.
"""

from cora.infrastructure.record_export import (
    ExportedRecord,
    hash_logbooks,
    hash_record,
    hash_streams,
)

_STREAM_ROW: dict[str, object] = {
    "event_id": "12345678-1234-5678-1234-567812345678",
    "event_type": "ProcedureRegistered",
    "version": 1,
}
_ACTIVITY_ROW: dict[str, object] = {
    "event_id": "aaaaaaaa-1234-5678-1234-567812345678",
    "step_kind": "setpoint",
    "payload": {"channel": "T_oven", "target_value": 423.0},
}


def _record() -> ExportedRecord:
    return ExportedRecord(
        streams=(_STREAM_ROW,),
        logbooks={"activity": (_ACTIVITY_ROW,)},
    )


def test_hash_record_is_stable_across_independently_built_equal_records() -> None:
    """Two structurally identical ExportedRecords (fresh dict/tuple copies,
    not the same objects) must hash identically -- this is what "the same
    database exported twice" reduces to at the data level."""
    first = ExportedRecord(
        streams=(dict(_STREAM_ROW),), logbooks={"activity": (dict(_ACTIVITY_ROW),)}
    )
    second = ExportedRecord(
        streams=(dict(_STREAM_ROW),), logbooks={"activity": (dict(_ACTIVITY_ROW),)}
    )
    assert hash_record(first) == hash_record(second)


def test_hash_record_changes_on_a_single_field_change_anywhere() -> None:
    baseline = hash_record(_record())

    changed_stream = ExportedRecord(
        streams=({**_STREAM_ROW, "version": 2},),
        logbooks={"activity": (_ACTIVITY_ROW,)},
    )
    assert hash_record(changed_stream) != baseline

    changed_logbook_row = dict(_ACTIVITY_ROW)
    changed_logbook_row["payload"] = {"channel": "T_oven", "target_value": 424.0}
    changed_logbook = ExportedRecord(
        streams=(_STREAM_ROW,),
        logbooks={"activity": (changed_logbook_row,)},
    )
    assert hash_record(changed_logbook) != baseline


def test_hash_record_is_sensitive_to_stream_row_order() -> None:
    """Stream order is significant (it is the replay order); reordering
    two rows must change the hash even though the SET of rows is the
    same."""
    row_a = {**_STREAM_ROW, "version": 1}
    row_b = {**_STREAM_ROW, "version": 2, "event_id": "bbbbbbbb-1234-5678-1234-567812345678"}
    forward = ExportedRecord(streams=(row_a, row_b), logbooks={})
    backward = ExportedRecord(streams=(row_b, row_a), logbooks={})
    assert hash_record(forward) != hash_record(backward)


def test_hash_record_is_insensitive_to_logbook_kind_key_order() -> None:
    """Kind keys sort themselves via json.dumps(sort_keys=True); insertion
    order into the `logbooks` dict must not affect the hash."""
    forward = ExportedRecord(
        streams=(),
        logbooks={"activity": (_ACTIVITY_ROW,), "outcome": ({"a": 1},)},
    )
    backward = ExportedRecord(
        streams=(),
        logbooks={"outcome": ({"a": 1},), "activity": (_ACTIVITY_ROW,)},
    )
    assert hash_record(forward) == hash_record(backward)


def test_hash_record_covers_both_tiers_not_just_one() -> None:
    """A record hash must differ from hashing either tier alone -- proof
    that hash_record is not accidentally ignoring one of the two."""
    record = _record()
    assert hash_record(record) != hash_streams(record.streams)
    assert hash_record(record) != hash_logbooks(record.logbooks)


def test_empty_record_hashes_deterministically() -> None:
    empty = ExportedRecord(streams=(), logbooks={})
    assert hash_record(empty) == hash_record(ExportedRecord(streams=(), logbooks={}))


def test_hash_streams_and_hash_logbooks_are_pinned_to_distinct_payload_types() -> None:
    """Same body, different payload_type, must hash differently: this is
    the whole point of binding payload_type into the PAE wrap."""
    record = _record()
    assert hash_streams(record.streams) != hash_logbooks({"x": record.streams})
