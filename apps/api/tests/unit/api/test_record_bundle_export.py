"""Unit tests for the S5d record-export operator command.

`export_record_bundles` needs a real Postgres connection (it opens a
`REPEATABLE READ` transaction and calls `export_record`), so the
end-to-end acceptance path lives in
`tests/integration/test_record_bundle_export_postgres.py`. What is
testable without a database -- the CLI surface, the exit code pin, the
non-empty-destination refusal, and the report's per-kind rendering --
is covered here against a synthetic `ExportedRecord` and `Manifest`,
mirroring `test_manifest.py`'s own synthetic-fixture approach.
"""

from pathlib import Path

import pytest

from cora.api.record_bundle_export import (
    _EXIT_CLEAN,  # pyright: ignore[reportPrivateUsage]
    _EXIT_REFUSED,  # pyright: ignore[reportPrivateUsage]
    _REFUSAL_ERRORS,  # pyright: ignore[reportPrivateUsage]
    FULL_DIRNAME,
    PUBLISHED_DIRNAME,
    _bundle_bytes,  # pyright: ignore[reportPrivateUsage]
    _kind_lines,  # pyright: ignore[reportPrivateUsage]
    _KindLine,  # pyright: ignore[reportPrivateUsage]
    _refuse_if_occupied,  # pyright: ignore[reportPrivateUsage]
    build_parser,
)
from cora.infrastructure.record_export import (
    BundleDestinationNotEmptyError,
    ExportedRecord,
    LogbookKindRowCountMismatchError,
    all_specs,
    build_manifest,
)


def _matching_source_row_count_by_logbook_kind(record: ExportedRecord) -> dict[str, int]:
    """Every registered kind's `source_row_count`, set to agree with
    `record.logbooks`, matching `test_manifest.py`'s own helper: these
    tests are about `_kind_lines`' rendering, not the S2b independent
    count, so the two counts must never diverge here."""
    return {spec.kind: len(record.logbooks.get(spec.kind, ())) for spec in all_specs()}


def test_exit_codes_are_zero_and_two() -> None:
    """Pinned per the module docstring's "Exit codes" section."""
    assert _EXIT_CLEAN == 0
    assert _EXIT_REFUSED == 2


def test_build_parser_requires_a_destination_positional() -> None:
    args = build_parser().parse_args(["/tmp/some-bundle-dir"])
    assert args.destination == Path("/tmp/some-bundle-dir")


def test_build_parser_with_no_destination_errors() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_refuse_if_occupied_is_silent_for_a_missing_or_empty_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    _refuse_if_occupied(missing)
    assert missing.is_dir()

    _refuse_if_occupied(missing)  # empty now; a second call must still be silent


def test_refuse_if_occupied_raises_for_a_non_empty_directory(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "leftover.txt").write_text("stale bundle content", encoding="utf-8")

    with pytest.raises(BundleDestinationNotEmptyError):
        _refuse_if_occupied(occupied)


def test_bundle_bytes_sums_every_file_recursively(tmp_path: Path) -> None:
    (tmp_path / "streams.jsonl").write_text("a" * 10, encoding="utf-8")
    logbooks = tmp_path / "logbooks"
    logbooks.mkdir()
    (logbooks / "activity.jsonl").write_text("b" * 5, encoding="utf-8")

    assert _bundle_bytes(tmp_path) == 15


def _synthetic_record() -> ExportedRecord:
    return ExportedRecord(
        streams=(),
        logbooks={"activity": ({"event_id": "1"}, {"event_id": "2"})},
        watermark=42,
        read_seconds_by_logbook_kind={"activity": 0.125},
    )


def test_kind_lines_reports_status_rows_and_read_seconds_for_an_included_kind() -> None:
    record = _synthetic_record()
    manifest = build_manifest(
        record,
        git_commit="deadbeef",
        source_row_count_by_logbook_kind=_matching_source_row_count_by_logbook_kind(record),
    )

    lines = {line.kind: line for line in _kind_lines(record, manifest)}

    activity = lines["activity"]
    assert activity.status == "included"
    assert activity.exported_row_count == 2
    assert activity.source_row_count == 2
    assert activity.read_seconds == pytest.approx(0.125)
    assert "read=0.125s" in activity.render()


def test_kind_lines_reports_zero_read_seconds_for_an_included_kind_never_actually_read() -> None:
    """An envelope-driven `included` kind whose envelope never occurred
    this export has no entry in `read_seconds_by_logbook_kind` at all
    (see `_export.py`'s docstring): that is a genuine zero read, not an
    unknown one, and must render as `0.000s`, never `n/a`."""
    record = ExportedRecord(streams=(), logbooks={}, watermark=0)
    manifest = build_manifest(
        record,
        git_commit="deadbeef",
        source_row_count_by_logbook_kind=_matching_source_row_count_by_logbook_kind(record),
    )

    lines = {line.kind: line for line in _kind_lines(record, manifest)}

    for kind, extent in manifest.extent_by_logbook_kind.items():
        if extent.status.value != "included":
            continue
        assert lines[kind].read_seconds == 0.0
        assert lines[kind].exported_row_count == 0


def test_kind_line_renders_n_a_for_a_kind_never_read() -> None:
    line = _KindLine(
        kind="widget",
        status="untraversed",
        exported_row_count=0,
        source_row_count=None,
        read_seconds=None,
    )
    assert "read=n/a" in line.render()
    assert "source=n/a" in line.render()


def test_dirnames_are_distinct() -> None:
    """The whole disclosure guarantee rests on `full/` and `published/`
    never being the same path."""
    assert FULL_DIRNAME != PUBLISHED_DIRNAME


def test_row_count_mismatch_is_not_a_refusal() -> None:
    """`LogbookKindRowCountMismatchError` must stay OUT of `_REFUSAL_ERRORS`:
    the module docstring's "Refusals, not tracebacks" section makes this a
    load-bearing distinction (an omission-at-origin signal must surface as
    a visible traceback, never get softened into a clean, retryable-looking
    `refused: ...` line the way the three genuine operator mistakes do).
    Pinned directly rather than only via the integration-level behavior in
    `test_record_bundle_export_postgres.py`, so widening this tuple (or
    swapping in a bare `except Exception`) fails fast, here, without
    needing a database."""
    assert LogbookKindRowCountMismatchError not in _REFUSAL_ERRORS
