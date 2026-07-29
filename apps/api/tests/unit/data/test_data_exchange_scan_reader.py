"""DataExchangeScanReader against synthetic Data Exchange files.

Files are built with h5py in tmp_path, mirroring what tomoscan plus
the 2-BM areaDetector layout actually write: `/exchange` stacks from
the one author, `/process/acquisition` metadata from the other. The
matrix pins the semantics the design locks: absent role datasets are
count 0 and never Unrecognized, commanded counts are None when the
OnFileClose groups are missing, a contradictory commanded count reads
unknowable, and a naive timestamp stays raw.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

from pathlib import Path

import h5py
import numpy as np
import pytest

from cora.data.adapters.data_exchange_scan_reader import DataExchangeScanReader
from cora.data.ports.scan_reader import Description, Unreadable, Unrecognized

pytestmark = pytest.mark.unit


def _write_scan(
    path: Path,
    *,
    projections: int = 5,
    flats: int | None = 2,
    darks: int | None = 2,
    theta: bool = True,
    num_angles: int | None = 5,
    flat_mode: str | None = "Start",
    num_flat_fields: int | None = 2,
    dark_mode: str | None = "Start",
    num_dark_fields: int | None = 2,
    start_date: str | None = "2026-07-29T10:15:30-05:00",
) -> None:
    with h5py.File(path, "w") as f:
        f.create_dataset("exchange/data", data=np.zeros((projections, 4, 4), dtype=np.uint16))
        if flats is not None:
            f.create_dataset("exchange/data_white", data=np.zeros((flats, 4, 4), dtype=np.uint16))
        if darks is not None:
            f.create_dataset("exchange/data_dark", data=np.zeros((darks, 4, 4), dtype=np.uint16))
        if theta:
            f.create_dataset("exchange/theta", data=np.linspace(0.0, 180.0, projections))
        if num_angles is not None:
            f.create_dataset("process/acquisition/rotation/num_angles", data=num_angles)
        if num_flat_fields is not None:
            f.create_dataset(
                "process/acquisition/flat_fields/num_flat_fields", data=num_flat_fields
            )
        if flat_mode is not None:
            f.create_dataset("process/acquisition/flat_fields/flat_field_mode", data=flat_mode)
        if num_dark_fields is not None:
            f.create_dataset(
                "process/acquisition/dark_fields/num_dark_fields", data=num_dark_fields
            )
        if dark_mode is not None:
            f.create_dataset("process/acquisition/dark_fields/dark_field_mode", data=dark_mode)
        if start_date is not None:
            f.create_dataset("process/acquisition/start_date", data=start_date)


def _reader(tmp_path: Path) -> DataExchangeScanReader:
    return DataExchangeScanReader(allowed_roots=(str(tmp_path),))


async def test_describe_clean_scan_reports_complete_counts(tmp_path: Path) -> None:
    scan = tmp_path / "scan_001.h5"
    _write_scan(scan)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.structurally_complete is True
    assert result.projection_count == 5
    assert result.flat_count == 2
    assert result.dark_count == 2
    assert result.invalid_count == 0
    assert result.commanded_projection_count == 5
    assert result.dropped_frame_count == 0
    assert result.projection_angles_deg is not None
    assert len(result.projection_angles_deg) == 5
    assert result.byte_size > 0
    assert result.media_type == "application/x-hdf5"


async def test_describe_theta_absent_reads_structurally_incomplete(tmp_path: Path) -> None:
    scan = tmp_path / "scan_002.h5"
    _write_scan(scan, theta=False)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.structurally_complete is False
    assert result.projection_angles_deg is None
    assert result.projection_count == 5


async def test_describe_missing_exchange_data_reads_unrecognized(tmp_path: Path) -> None:
    other = tmp_path / "not_a_scan.h5"
    with h5py.File(other, "w") as f:
        f.create_dataset("something/else", data=np.zeros(3))

    result = await _reader(tmp_path).describe(locator_uri=other.as_uri())

    assert isinstance(result, Unrecognized)


async def test_describe_no_flats_scan_reads_count_zero_not_unrecognized(tmp_path: Path) -> None:
    """FlatFieldMode=None is a designed acquisition mode; absent role
    datasets are counts, never a layout verdict."""
    scan = tmp_path / "scan_003.h5"
    _write_scan(scan, flats=None, darks=None, flat_mode="None", dark_mode="None")

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.flat_count == 0
    assert result.dark_count == 0
    assert result.commanded_flat_count == 0
    assert result.commanded_dark_count == 0
    assert result.structurally_complete is True


async def test_describe_missing_process_groups_reads_commanded_none(tmp_path: Path) -> None:
    """The OnFileClose groups do not exist in a crashed file; commanded
    counts read unknowable, not zero."""
    scan = tmp_path / "scan_004.h5"
    _write_scan(
        scan,
        num_angles=None,
        flat_mode=None,
        num_flat_fields=None,
        dark_mode=None,
        num_dark_fields=None,
    )

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count is None
    assert result.commanded_flat_count is None
    assert result.commanded_dark_count is None
    assert result.dropped_frame_count is None


async def test_describe_shortfall_derives_from_commanded_count(tmp_path: Path) -> None:
    scan = tmp_path / "scan_005.h5"
    _write_scan(scan, projections=3, num_angles=5, theta=True)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.dropped_frame_count == 2


async def test_describe_contradictory_commanded_count_reads_unknowable(tmp_path: Path) -> None:
    """More captured than commanded means the source contradicts itself;
    a fabricated negative would poison downstream arithmetic."""
    scan = tmp_path / "scan_006.h5"
    _write_scan(scan, projections=5, num_angles=3)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.dropped_frame_count is None


@pytest.mark.parametrize(
    ("mode", "configured", "expected"),
    [
        ("Start", 2, 2),
        ("End", 2, 2),
        ("Both", 2, 4),
        ("None", 2, 0),
        ("Weird", 2, None),
    ],
)
async def test_describe_flat_mode_arithmetic_matches_tomoscan(
    tmp_path: Path, mode: str, configured: int, expected: int | None
) -> None:
    scan = tmp_path / f"scan_mode_{mode}.h5"
    _write_scan(scan, flat_mode=mode, num_flat_fields=configured)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_flat_count == expected


async def test_describe_aware_start_date_parses(tmp_path: Path) -> None:
    scan = tmp_path / "scan_007.h5"
    _write_scan(scan, start_date="2026-07-29T10:15:30-05:00")

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.start_date is not None
    assert result.start_date.utcoffset() is not None
    assert result.start_date_raw == "2026-07-29T10:15:30-05:00"


async def test_describe_naive_start_date_stays_raw(tmp_path: Path) -> None:
    """A naive string must not be assigned a zone; the site timezone
    rule is an open staff question."""
    scan = tmp_path / "scan_008.h5"
    _write_scan(scan, start_date="2026-07-29T10:15:30")

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.start_date is None
    assert result.start_date_raw == "2026-07-29T10:15:30"


async def test_describe_non_hdf5_bytes_reads_unreadable(tmp_path: Path) -> None:
    bogus = tmp_path / "scan.h5"
    bogus.write_bytes(b"this is not an HDF5 file")

    result = await _reader(tmp_path).describe(locator_uri=bogus.as_uri())

    assert isinstance(result, Unreadable)


async def test_describe_path_outside_roots_reads_unreadable(tmp_path: Path) -> None:
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside.h5"
    _write_scan(outside)
    reader = DataExchangeScanReader(allowed_roots=(str(inside),))

    result = await reader.describe(locator_uri=outside.as_uri())

    assert isinstance(result, Unreadable)


async def test_describe_non_file_scheme_reads_unreadable(tmp_path: Path) -> None:
    result = await _reader(tmp_path).describe(locator_uri="https://example.org/scan.h5")

    assert isinstance(result, Unreadable)
