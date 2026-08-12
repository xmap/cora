"""Unit tests for the bundle writer and its on-disk round trip.

`write_bundle` is the step that turns in-memory structures into an
artifact somebody can archive. The property that matters is not "the
files exist" but "the body reassembled from those files hashes to what
the in-memory record hashed to", because that is the only thing a
reviewer's verification actually rests on.

The subprocess test that runs `scripts/verify_record_hash.py` against a
real bundle with no `cora` on the path lives in
`test_standalone_verifier.py`, beside the rest of that script's tests.
"""

import json
from pathlib import Path

import pytest

from cora.infrastructure.record_export import (
    LOGBOOKS_DIR,
    MANIFEST_NAME,
    RECORD_PAYLOAD_TYPE,
    STREAMS_NAME,
    BundleDestinationNotEmptyError,
    ExportedRecord,
    MalformedBundleError,
    build_manifest,
    hash_record,
    hash_redacted_record,
    read_bundle_body,
    write_bundle,
)
from cora.infrastructure.record_export._redaction import RedactedRecord
from cora.shared.content_hash import compute_content_hash

_COMMIT = "0" * 40


def _record() -> ExportedRecord:
    return ExportedRecord(
        streams=(
            {
                "stream_type": "Run",
                "stream_id": "01900000-0000-7000-8000-0000000000a1",
                "event_type": "RunStarted",
                "schema_version": 1,
                "payload": {"note": "first"},
            },
            {
                "stream_type": "Run",
                "stream_id": "01900000-0000-7000-8000-0000000000a1",
                "event_type": "RunCompleted",
                "schema_version": 2,
                "payload": {"note": "second"},
            },
        ),
        logbooks={
            "activity": (
                {"event_id": "a1", "step_kind": "setpoint", "payload": {"channel": "2bma:x"}},
                {"event_id": "a2", "step_kind": "check", "payload": {"channel": "2bma:flux"}},
            ),
            "observation": ({"event_id": "o1", "value": 1.5, "is_simulated": True},),
        },
    )


def _manifest(record: ExportedRecord) -> object:
    return build_manifest(record, watermark=42, git_commit=_COMMIT)


def test_write_bundle_lays_out_the_names_the_design_fixed(tmp_path: Path) -> None:
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    bundle = tmp_path / "b"
    assert (bundle / MANIFEST_NAME).is_file()
    assert (bundle / STREAMS_NAME).is_file()
    assert sorted(p.name for p in (bundle / LOGBOOKS_DIR).iterdir()) == [
        "activity.jsonl",
        "observation.jsonl",
    ]


def test_streams_file_is_one_json_object_per_line_in_export_order(tmp_path: Path) -> None:
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    lines = (tmp_path / "b" / STREAMS_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["event_type"] for line in lines] == ["RunStarted", "RunCompleted"]


def test_reassembled_body_hashes_to_the_in_memory_record_hash(tmp_path: Path) -> None:
    """The whole point of the bundle: what came back off disk is what was hashed."""
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    body = read_bundle_body(tmp_path / "b")
    assert compute_content_hash(RECORD_PAYLOAD_TYPE, body) == hash_record(record)


def test_editing_one_value_on_disk_changed_the_hash(tmp_path: Path) -> None:
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    path = tmp_path / "b" / LOGBOOKS_DIR / "activity.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace("2bma:x", "2bma:y"), encoding="utf-8")

    body = read_bundle_body(tmp_path / "b")
    assert compute_content_hash(RECORD_PAYLOAD_TYPE, body) != hash_record(record)


def test_deleting_a_whole_logbook_kind_breaks_the_hash(tmp_path: Path) -> None:
    """A per-file check would pass here. Only the reassembled body catches it."""
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]
    (tmp_path / "b" / LOGBOOKS_DIR / "observation.jsonl").unlink()

    body = read_bundle_body(tmp_path / "b")
    assert compute_content_hash(RECORD_PAYLOAD_TYPE, body) != hash_record(record)


def test_reordering_lines_breaks_the_hash(tmp_path: Path) -> None:
    """Order is part of the record (F2's order key), not presentation."""
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    path = tmp_path / "b" / STREAMS_NAME
    path.write_text(
        "".join(f"{line}\n" for line in reversed(path.read_text(encoding="utf-8").splitlines())),
        encoding="utf-8",
    )

    body = read_bundle_body(tmp_path / "b")
    assert compute_content_hash(RECORD_PAYLOAD_TYPE, body) != hash_record(record)


def test_writing_twice_into_one_directory_refuses(tmp_path: Path) -> None:
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]

    with pytest.raises(BundleDestinationNotEmptyError):
        write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]


def test_bundle_without_manifest_refuses_to_read(tmp_path: Path) -> None:
    """What an interrupted export leaves behind: rows, no manifest."""
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]
    (tmp_path / "b" / MANIFEST_NAME).unlink()

    with pytest.raises(MalformedBundleError, match=MANIFEST_NAME):
        read_bundle_body(tmp_path / "b")


def test_non_object_line_refuses_rather_than_reading_partially(tmp_path: Path) -> None:
    record = _record()
    write_bundle(record, _manifest(record), tmp_path / "b")  # pyright: ignore[reportArgumentType]
    (tmp_path / "b" / STREAMS_NAME).write_text('["not an object"]\n', encoding="utf-8")

    with pytest.raises(MalformedBundleError, match="not a JSON object"):
        read_bundle_body(tmp_path / "b")


def test_manifest_carries_h3_only_when_a_redacted_record_is_supplied(tmp_path: Path) -> None:
    record = _record()
    redacted = RedactedRecord(streams=record.streams, logbooks=record.logbooks)

    without = build_manifest(record, watermark=42, git_commit=_COMMIT)
    with_h3 = build_manifest(record, watermark=42, git_commit=_COMMIT, redacted=redacted)

    assert without.published_record_hash is None
    assert with_h3.published_record_hash == hash_redacted_record(redacted)


def test_h1_and_h3_differ_even_when_redaction_changed_nothing() -> None:
    """The payload type keeps them apart, so a reader can always tell a
    published record from a full one by its hash alone."""
    record = _record()
    redacted = RedactedRecord(streams=record.streams, logbooks=record.logbooks)

    assert hash_record(record) != hash_redacted_record(redacted)
