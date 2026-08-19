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
