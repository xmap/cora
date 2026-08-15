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
    ManifestRecordMismatchError,
    RedactionResult,
    TokenMap,
    build_manifest,
    hash_record,
    hash_redacted_record,
    hash_redaction_profile,
    read_bundle_body,
    redact_record,
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
    return build_manifest(record, git_commit=_COMMIT)


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


def test_manifest_carries_h3_only_when_a_redaction_is_supplied(tmp_path: Path) -> None:
    record = _record()
    redacted = RedactedRecord(streams=record.streams, logbooks=record.logbooks)
    redaction = RedactionResult(
        redacted_record=redacted,
        token_map=TokenMap(),
        unfired_tier2_clearances=frozenset(),
        unfired_tier1_fields=frozenset(),
    )

    without = build_manifest(record, git_commit=_COMMIT)
    with_h3 = build_manifest(record, git_commit=_COMMIT, redaction=redaction)

    assert without.published_record_hash is None
    assert with_h3.published_record_hash == hash_redacted_record(redacted)


def test_h1_and_h3_differ_even_when_redaction_changed_nothing() -> None:
    """The payload type keeps them apart, so a reader can always tell a
    published record from a full one by its hash alone."""
    record = _record()
    redacted = RedactedRecord(streams=record.streams, logbooks=record.logbooks)

    assert hash_record(record) != hash_redacted_record(redacted)


def _other_record() -> ExportedRecord:
    """A record with different content from `_record()`, so its H1/H3
    cannot coincidentally match a manifest built for the other one."""
    return ExportedRecord(
        streams=(
            {
                "stream_type": "Run",
                "stream_id": "01900000-0000-7000-8000-0000000000ff",
                "event_type": "RunStarted",
                "schema_version": 1,
                "payload": {"note": "a different run entirely"},
            },
        ),
        logbooks={},
    )


def test_write_bundle_refuses_when_the_manifest_describes_a_different_record(
    tmp_path: Path,
) -> None:
    """Unredacted case: `write_bundle` must not accept a manifest built
    from one record next to a different record. Before this guard
    existed, neither argument was checked against the other at all."""
    manifest = build_manifest(_record(), git_commit=_COMMIT)

    with pytest.raises(ManifestRecordMismatchError):
        write_bundle(_other_record(), manifest, tmp_path / "b")  # pyright: ignore[reportArgumentType]

    assert not (tmp_path / "b").exists()


def _record_redactable_by_the_real_pipeline() -> ExportedRecord:
    """A record whose stream rows carry every fixed column
    `Tier1Redactor.redact_row` reads directly (`_record()`'s rows are
    minimal and lack `transaction_id` / `event_id` / etc.), so it can go
    through the REAL `redact_record` rather than an aliased
    `RedactedRecord` copy. Tokenizing `stream_id` to a random surrogate
    changes the body content, which is what makes H3 actually differ
    from hashing the unredacted record -- an aliased copy is
    byte-identical and cannot reproduce a real mismatch at all."""
    return ExportedRecord(
        streams=(
            {
                "stream_type": "Run",
                "stream_id": "01900000-0000-7000-8000-0000000000a1",
                "event_type": "RunStarted",
                "schema_version": 1,
                "occurred_at": "2026-05-15T12:00:00+00:00",
                "recorded_at": "2026-05-15T12:00:00+00:00",
                "transaction_id": 1,
                "event_id": "01900000-0000-7000-8000-0000000000e1",
                "correlation_id": None,
                "causation_id": None,
                "principal_id": None,
                "payload": {"note": "first"},
            },
        ),
        logbooks={},
    )


def _redact(record: ExportedRecord) -> RedactionResult:
    return redact_record(record, expected_redaction_profile_hash=hash_redaction_profile())


def test_write_bundle_refuses_an_unredacted_record_beside_a_manifest_carrying_h3(
    tmp_path: Path,
) -> None:
    """The exact reproduction: a manifest whose `published_record_hash`
    (H3) was computed from the REAL redacted record, handed to
    `write_bundle` alongside the UNREDACTED record instead. Before this
    guard existed, this wrote a fully unredacted bundle that the default
    verifier printed `OK` for under a `--published` label."""
    record = _record_redactable_by_the_real_pipeline()
    redaction = _redact(record)
    manifest = build_manifest(record, git_commit=_COMMIT, redaction=redaction)

    with pytest.raises(ManifestRecordMismatchError):
        write_bundle(record, manifest, tmp_path / "b")  # pyright: ignore[reportArgumentType]

    assert not (tmp_path / "b").exists()


def test_write_bundle_refuses_a_redacted_record_beside_an_h1_only_manifest(
    tmp_path: Path,
) -> None:
    """The mirror direction: a manifest with NO `published_record_hash`
    (an unredacted-bundle manifest) handed the REDACTED record instead of
    the one it was actually built from. Tokenized `stream_id`s and
    dropped columns mean the redacted body cannot reproduce H1."""
    record = _record_redactable_by_the_real_pipeline()
    redaction = _redact(record)
    manifest = build_manifest(record, git_commit=_COMMIT)

    with pytest.raises(ManifestRecordMismatchError):
        write_bundle(redaction.redacted_record, manifest, tmp_path / "b")

    assert not (tmp_path / "b").exists()


def test_write_bundle_accepts_the_redacted_record_beside_its_own_h3_manifest(
    tmp_path: Path,
) -> None:
    """The positive case: the record `build_manifest` actually hashed for
    H3 is exactly what `write_bundle` was handed, so it must proceed."""
    record = _record_redactable_by_the_real_pipeline()
    redaction = _redact(record)
    manifest = build_manifest(record, git_commit=_COMMIT, redaction=redaction)

    bundle = write_bundle(redaction.redacted_record, manifest, tmp_path / "b")
    assert (bundle / MANIFEST_NAME).is_file()
