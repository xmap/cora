"""End-to-end (loopback, no SSH) tests for `_remote_scan_probe._handle`.

Exercises the actual composition this module exists for: constructing
`DataExchangeScanReader` / `PosixChecksumAdapter` -- the SAME classes the
local, non-SSH ingest path uses, unchanged -- from a JSON request, and
serializing their result back to a JSON-safe dict. `test_ssh_probe.py`
covers the transport (never reaching a real host here); this file proves
the two composed adapters still parse a real HDF5 file and produce a
verdict `_response_to_result` on the client side can round-trip.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# reportPrivateUsage: this file's whole point is exercising the
# entrypoint's own request handler directly (a loopback, no-SSH
# end-to-end check), so importing `_handle` is deliberate, not a leak.
# pyright: reportPrivateUsage=false

import io
import os
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pytest

from cora.data._remote_scan_probe import MAX_LOCATE_MATCHES, _handle

pytestmark = pytest.mark.unit


def _write_scan(path: Path) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset("exchange/data", data=np.zeros((5, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/data_white", data=np.zeros((2, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/data_dark", data=np.zeros((2, 4, 4), dtype=np.uint16))
        f.create_dataset("exchange/theta", data=np.linspace(0.0, 180.0, 5))
        f.create_dataset("process/acquisition/start_date", data="2026-08-18T06:21:17-05:00")
        f.create_dataset("process/acquisition/end_date", data="2026-08-18T06:23:41-05:00")


async def test_describe_op_returns_a_json_safe_description(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    _write_scan(scan_path)

    response = await _handle(
        {
            "op": "describe",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": [str(tmp_path)],
            "captured_at_source": "end_date",
        }
    )

    assert response["kind"] == "Description"
    assert response["projection_count"] == 5
    assert response["structurally_complete"] is True
    assert response["captured_at_source"] == "end_date"
    assert response["captured_at"] == "2026-08-18T06:23:41-05:00"
    # Every value must round-trip through json.dumps (the actual wire
    # format): a tuple would silently become a list, which is fine, but
    # anything json can't encode would be a real defect here.
    import json

    json.dumps(response)


async def test_describe_op_refuses_a_path_outside_allowed_roots(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    _write_scan(scan_path)

    response = await _handle(
        {
            "op": "describe",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": ["/somewhere/else"],
        }
    )

    assert response["kind"] == "Unreadable"


async def test_checksum_op_returns_a_json_safe_computed_checksum(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    scan_path.write_bytes(b"deterministic bytes for a digest")

    response = await _handle(
        {
            "op": "checksum",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": [str(tmp_path)],
            "supply_id": "01900000-0000-7000-8000-000000000001",
        }
    )

    assert response["kind"] == "ComputedChecksum"
    assert response["algorithm"] == "sha256"
    assert response["byte_size"] == len(b"deterministic bytes for a digest")


async def test_checksum_op_with_a_missing_supply_id_returns_a_probe_error(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    scan_path.write_bytes(b"x")

    response = await _handle(
        {"op": "checksum", "locator_uri": scan_path.as_uri(), "allowed_roots": [str(tmp_path)]}
    )

    assert response["kind"] == "ProbeError"


async def test_checksum_op_with_a_malformed_supply_id_returns_a_probe_error(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    scan_path.write_bytes(b"x")

    response = await _handle(
        {
            "op": "checksum",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": [str(tmp_path)],
            "supply_id": "not-a-uuid",
        }
    )

    assert response["kind"] == "ProbeError"


async def test_unknown_op_returns_a_probe_error_not_an_exception() -> None:
    response = await _handle({"op": "not-a-real-op", "locator_uri": "file:///x"})
    assert response["kind"] == "ProbeError"


async def test_malformed_request_returns_a_probe_error() -> None:
    response = await _handle({"op": "describe"})
    assert response["kind"] == "ProbeError"


async def test_describe_op_on_hdf5_without_the_exchange_layout_returns_unrecognized(
    tmp_path: Path,
) -> None:
    """Readable HDF5 that is not a data-exchange scan is `Unrecognized`,
    a distinct verdict from `Unreadable` (refused, absent, or not HDF5
    at all), and the two serialize down different arms."""
    other_hdf5 = tmp_path / "other.h5"
    with h5py.File(other_hdf5, "w") as f:
        f.create_dataset("something/else", data=np.zeros((2, 2), dtype=np.uint16))

    response = await _handle(
        {
            "op": "describe",
            "locator_uri": other_hdf5.as_uri(),
            "allowed_roots": [str(tmp_path)],
        }
    )

    assert response["kind"] == "Unrecognized"


async def test_checksum_op_outside_allowed_roots_returns_unreachable(tmp_path: Path) -> None:
    scan_path = tmp_path / "scan.h5"
    scan_path.write_bytes(b"x")

    response = await _handle(
        {
            "op": "checksum",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": ["/somewhere/else"],
            "supply_id": "01900000-0000-7000-8000-000000000001",
        }
    )

    assert response["kind"] == "Unreachable"


async def test_main_emits_exactly_one_json_line_for_one_stdin_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The actual contract with the SSH client, which reads
    `stdout.splitlines()[0]`: one request line in, exactly one JSON line
    out. Asserted here rather than left to inspection because a stray
    print or a second line would silently corrupt every response."""
    import json

    from cora.data._remote_scan_probe import _main

    scan_path = tmp_path / "scan.h5"
    _write_scan(scan_path)
    request = json.dumps(
        {
            "op": "describe",
            "locator_uri": scan_path.as_uri(),
            "allowed_roots": [str(tmp_path)],
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(request + "\n"))

    await _main()

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "Description"


async def test_main_turns_unparseable_stdin_into_a_probe_error_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Truncated or garbled stdin must still produce one JSON line and a
    zero exit: a traceback on stderr with nothing on stdout is what the
    client reports as an unparseable response, losing the real reason."""
    import json

    from cora.data._remote_scan_probe import _main

    monkeypatch.setattr("sys.stdin", io.StringIO("{not json\n"))

    await _main()

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "ProbeError"


async def test_main_rejects_a_json_request_that_is_not_an_object(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from cora.data._remote_scan_probe import _main

    monkeypatch.setattr("sys.stdin", io.StringIO('["a", "list"]\n'))

    await _main()

    assert json.loads(capsys.readouterr().out.splitlines()[0])["kind"] == "ProbeError"


async def test_main_catch_all_never_renders_the_exceptions_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exception TYPE only, never `str(exc)`: the paths this process
    walks embed a PI surname, and an `OSError` subclass renders the
    filename it failed on. A message carrying that fragment must never
    reach the response, only the class name."""
    import json

    from cora.data import _remote_scan_probe

    secret_fragment = "Smith-1015116/scan_005.h5"

    async def _boom(request: dict[str, Any]) -> dict[str, Any]:
        raise OSError(f"could not stat {secret_fragment}")

    monkeypatch.setattr(_remote_scan_probe, "_handle", _boom)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"op": "describe", "locator_uri": "file:///x"}) + "\n")
    )

    await _remote_scan_probe._main()

    response = json.loads(capsys.readouterr().out.splitlines()[0])
    assert response["kind"] == "ProbeError"
    assert response["detail"] == "unhandled OSError"
    assert secret_fragment not in response["detail"]


async def test_main_discards_a_stray_stdout_write_from_handle_and_never_leaks_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`describe` and `checksum` both make `_log` calls that write to
    stdout by default, and stdout IS the protocol: the client parses the
    FIRST line as the verdict. `_handle` here stands in for a call that
    logs (and even `print`s) a path carrying a surname before returning
    its real verdict; only that verdict may reach stdout."""
    import json

    from cora.data import _remote_scan_probe

    secret_fragment = "Smith-1015116/scan_005.h5"

    async def _noisy_handle(request: dict[str, Any]) -> dict[str, Any]:
        print(f"resolved locator to {secret_fragment}")
        print(f"also logged: {secret_fragment}")
        return {"kind": "Located", "matches": [], "match_count": 0}

    monkeypatch.setattr(_remote_scan_probe, "_handle", _noisy_handle)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"op": "describe", "locator_uri": "file:///x"}) + "\n")
    )

    await _remote_scan_probe._main()

    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"kind": "Located", "matches": [], "match_count": 0}
    assert secret_fragment not in out


def _durable_tree(
    root: Path, *, experiment: str, filename: str = "scan_005.h5", month: str = "2026-08"
) -> Path:
    """A miniature of 2-BM's durable tree: `<root>/<month>/<exp>/data/<file>`."""
    data_directory = root / month / experiment / "data"
    data_directory.mkdir(parents=True, exist_ok=True)
    scan_path = data_directory / filename
    scan_path.write_bytes(b"bytes")
    return scan_path


def _locate_request(root: Path, **overrides: object) -> dict[str, object]:
    request: dict[str, object] = {
        "op": "locate",
        "root": str(root),
        "allowed_roots": [str(root)],
        "months": ["2026-08"],
        "directory_suffix": "-1015116",
        "subdirectory": "data",
        "filename": "scan_005.h5",
    }
    request.update(overrides)
    return request


async def test_locate_op_finds_the_experiment_directory_by_proposal_suffix(
    tmp_path: Path,
) -> None:
    """The whole point of the op: CORA holds the proposal number and the
    filename but never the PI surname the directory is named after, so
    the match has to come from the suffix alone. The second experiment
    exists so a match proves suffix filtering, not "the only entry"."""
    scan_path = _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")
    _durable_tree(tmp_path, experiment="2026-08-Someone-9999999")

    response = await _handle(_locate_request(tmp_path))

    assert response["kind"] == "Located"
    assert response["match_count"] == 1
    assert response["matches"] == [
        {"path": str(scan_path), "modified_at": scan_path.stat().st_mtime}
    ]


async def test_locate_op_reports_the_matched_files_own_modification_time(
    tmp_path: Path,
) -> None:
    """`modified_at` is the SUBSTRATE's timestamp, read on the side that
    can see the file, not derived or defaulted; a known `st_mtime` set
    via `os.utime` must come back unchanged."""
    scan_path = _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")
    known_mtime = 1755000000.0
    os.utime(scan_path, (known_mtime, known_mtime))

    response = await _handle(_locate_request(tmp_path))

    assert response["matches"][0]["modified_at"] == known_mtime


async def test_locate_op_reports_every_match_when_the_suffix_is_ambiguous(
    tmp_path: Path,
) -> None:
    _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")
    _durable_tree(tmp_path, experiment="2026-08-Other-1015116")

    response = await _handle(_locate_request(tmp_path))

    assert response["match_count"] == 2


async def test_locate_op_with_no_match_reports_zero_rather_than_failing(tmp_path: Path) -> None:
    _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")

    response = await _handle(_locate_request(tmp_path, directory_suffix="-7777777"))

    assert response["kind"] == "Located"
    assert response["match_count"] == 0
    assert response["matches"] == []


async def test_locate_op_with_an_absent_month_directory_reports_zero(tmp_path: Path) -> None:
    response = await _handle(_locate_request(tmp_path, months=["1999-01"]))

    assert response["kind"] == "Located"
    assert response["match_count"] == 0


async def test_locate_op_finds_an_experiment_filed_under_a_neighbouring_month(
    tmp_path: Path,
) -> None:
    """Why `months` is a list. Beamtime can straddle a month boundary,
    so the experiment folder can be filed under the month the beamtime
    was scheduled in rather than the month the scan ran. Searching only
    the scan's own month would miss it silently, and since no match
    means keep waiting, it would never be found."""
    scan_path = _durable_tree(tmp_path, experiment="2026-07-Haridy-1015116", month="2026-07")

    response = await _handle(_locate_request(tmp_path, months=["2026-08", "2026-07"]))

    assert response["match_count"] == 1
    assert response["matches"] == [
        {"path": str(scan_path), "modified_at": scan_path.stat().st_mtime}
    ]


async def test_locate_op_refuses_an_empty_month_list(tmp_path: Path) -> None:
    response = await _handle(_locate_request(tmp_path, months=[]))

    assert response["kind"] == "ProbeError"
    assert "months" in str(response["detail"])


async def test_locate_op_refuses_more_months_than_the_cap(tmp_path: Path) -> None:
    """The caller sends a month and its neighbours; a request to sweep
    the whole archive is a misuse, and the tree goes back to 2020."""
    response = await _handle(
        _locate_request(tmp_path, months=[f"2026-{month:02d}" for month in range(1, 9)])
    )

    assert response["kind"] == "ProbeError"
    assert "months" in str(response["detail"])


@pytest.mark.parametrize(
    "segment",
    ["../2026-08", "2026-08/..", ".", "..", "", "2026-08\x00", " 2026-08"],
)
async def test_locate_op_refuses_a_month_that_is_not_one_safe_segment(
    tmp_path: Path, segment: str
) -> None:
    response = await _handle(_locate_request(tmp_path, months=[segment]))

    assert response["kind"] == "ProbeError"
    assert "months" in str(response["detail"])


async def test_locate_op_refuses_a_filename_carrying_a_separator(tmp_path: Path) -> None:
    _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")

    response = await _handle(_locate_request(tmp_path, filename="../../etc/passwd"))

    assert response["kind"] == "ProbeError"
    assert "filename" in str(response["detail"])


async def test_locate_op_refuses_a_root_outside_allowed_roots(tmp_path: Path) -> None:
    _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")

    response = await _handle(
        _locate_request(tmp_path, allowed_roots=[str(tmp_path / "somewhere-else")])
    )

    assert response["kind"] == "ProbeError"


async def test_locate_op_refuses_a_symlink_that_escapes_the_allowed_root(
    tmp_path: Path,
) -> None:
    """Confinement is re-checked AFTER resolution, so a data directory
    symlinked out of the tree is declined rather than followed. The
    matched entry is inside the root by construction; only what it
    resolves to is not, which is the case a pre-resolution check misses."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "scan_005.h5").write_bytes(b"bytes")
    root = tmp_path / "gdata"
    experiment = root / "2026-08" / "2026-08-Haridy-1015116"
    experiment.mkdir(parents=True)
    (experiment / "data").symlink_to(outside, target_is_directory=True)

    response = await _handle(_locate_request(root, allowed_roots=[str(root)]))

    assert response["kind"] == "Located"
    assert response["match_count"] == 0


def _raise_on_second_call(
    monkeypatch: pytest.MonkeyPatch, *, method_name: str, target: Path, detail: str
) -> None:
    """Let the first call to `Path.<method_name>` on `target` behave
    normally, then raise a bare `OSError(detail)` on every call after
    that. Isolates a specific call site (one that calls the method a
    second time) from an earlier call the same code path also makes
    internally (`is_file` calls `stat` itself), so a guard can be pinned
    without also tripping over that internal call."""
    original = getattr(Path, method_name)
    calls = {"count": 0}

    def _patched(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == target:
            calls["count"] += 1
            if calls["count"] > 1:
                raise OSError(detail)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, method_name, _patched)


def _raise_always(
    monkeypatch: pytest.MonkeyPatch, *, method_name: str, target: Path, detail: str
) -> None:
    original = getattr(Path, method_name)

    def _patched(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == target:
            raise OSError(detail)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, method_name, _patched)


async def test_locate_op_keeps_stat_inside_the_error_guard_and_never_leaks_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`stat` must raise from INSIDE the same `try/except OSError` that
    guards `resolve` and `is_file`. `is_file` calls `stat` internally, so
    the first call on the candidate is left alone (it is how `is_file`
    itself succeeds) and only the explicit `resolved.stat()` call --
    the second one -- is made to fail."""
    import json

    scan_path = _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")
    secret_fragment = "Haridy-1015116"
    _raise_on_second_call(
        monkeypatch,
        method_name="stat",
        target=scan_path.resolve(),
        detail=f"could not stat {scan_path.resolve()}",
    )

    response = await _handle(_locate_request(tmp_path))

    assert response["kind"] == "Located"
    assert response["matches"] == []
    assert secret_fragment not in json.dumps(response)


async def test_locate_op_keeps_is_file_inside_the_error_guard_and_never_leaks_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mutation this whole commit was written to fix: `is_file`
    raising outside the guard used to leak a path embedding a PI
    surname through `_main`'s catch-all."""
    import json

    scan_path = _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116")
    secret_fragment = "Haridy-1015116"
    _raise_always(
        monkeypatch,
        method_name="stat",
        target=scan_path.resolve(),
        detail=f"could not stat {scan_path.resolve()}",
    )

    response = await _handle(_locate_request(tmp_path))

    assert response["kind"] == "Located"
    assert response["matches"] == []
    assert secret_fragment not in json.dumps(response)


def _many_matching_experiments(root: Path, count: int) -> None:
    for index in range(count):
        _durable_tree(root, experiment=f"2026-08-Person{index:02d}-1015116")


async def test_locate_op_caps_returned_matches_at_max_locate_matches(tmp_path: Path) -> None:
    _many_matching_experiments(tmp_path, MAX_LOCATE_MATCHES + 3)

    response = await _handle(_locate_request(tmp_path))

    assert response["kind"] == "Located"
    assert len(response["matches"]) == MAX_LOCATE_MATCHES


async def test_locate_op_reports_match_count_uncapped_beyond_max_locate_matches(
    tmp_path: Path,
) -> None:
    """`match_count` is deliberately reported UNCAPPED beside a truncated
    `matches` list, so a caller can tell 2 matches from 50 even though it
    only ever sees the first few."""
    total = MAX_LOCATE_MATCHES + 3
    _many_matching_experiments(tmp_path, total)

    response = await _handle(_locate_request(tmp_path))

    assert response["match_count"] == total
    assert response["match_count"] > MAX_LOCATE_MATCHES


async def test_locate_op_directory_suffix_match_is_endswith_not_substring(
    tmp_path: Path,
) -> None:
    """The proposal suffix carries a leading hyphen precisely so a
    directory that merely contains it in the middle, rather than ending
    with it, is refused."""
    _durable_tree(tmp_path, experiment="2026-08-Haridy-1015116-extra")

    response = await _handle(_locate_request(tmp_path))

    assert response["kind"] == "Located"
    assert response["match_count"] == 0


async def test_locate_op_orders_matches_deterministically_by_sorted_directory_name(
    tmp_path: Path,
) -> None:
    zeta_path = _durable_tree(tmp_path, experiment="2026-08-Zeta-1015116")
    alpha_path = _durable_tree(tmp_path, experiment="2026-08-Alpha-1015116")

    response = await _handle(_locate_request(tmp_path))

    assert [match["path"] for match in response["matches"]] == [str(alpha_path), str(zeta_path)]
