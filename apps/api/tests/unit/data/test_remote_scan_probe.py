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
from pathlib import Path

import h5py
import numpy as np
import pytest

from cora.data._remote_scan_probe import _handle

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


def _durable_tree(root: Path, *, experiment: str, filename: str = "scan_005.h5") -> Path:
    """A miniature of 2-BM's durable tree: `<root>/<month>/<exp>/data/<file>`."""
    data_directory = root / "2026-08" / experiment / "data"
    data_directory.mkdir(parents=True, exist_ok=True)
    scan_path = data_directory / filename
    scan_path.write_bytes(b"bytes")
    return scan_path


def _locate_request(root: Path, **overrides: object) -> dict[str, object]:
    request: dict[str, object] = {
        "op": "locate",
        "root": str(root),
        "allowed_roots": [str(root)],
        "month": "2026-08",
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
    assert response["paths"] == [str(scan_path)]


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
    assert response["paths"] == []


async def test_locate_op_with_an_absent_month_directory_reports_zero(tmp_path: Path) -> None:
    response = await _handle(_locate_request(tmp_path, month="1999-01"))

    assert response["kind"] == "Located"
    assert response["match_count"] == 0


@pytest.mark.parametrize(
    "segment",
    ["../2026-08", "2026-08/..", ".", "..", "", "2026-08\x00", " 2026-08"],
)
async def test_locate_op_refuses_a_month_that_is_not_one_safe_segment(
    tmp_path: Path, segment: str
) -> None:
    response = await _handle(_locate_request(tmp_path, month=segment))

    assert response["kind"] == "ProbeError"
    assert "month" in str(response["detail"])


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
