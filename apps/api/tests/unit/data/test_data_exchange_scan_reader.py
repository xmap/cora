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


def _scalar(value: int | str, *, boxed: bool) -> object:
    """A scalar as the two shapes real writers use.

    2-BM writes every `/process/acquisition` scalar as a 1-element
    array, not as a 0-dimensional dataset, measured against a real scan
    file. Tests that only ever wrote the 0-d shape were green while the
    reader could not read a single commanded count at the beamline, so
    the shape is a fixture parameter rather than an assumption.
    """
    return [value] if boxed else value


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
    end_date: str | None = None,
    boxed_scalars: bool = False,
) -> None:
    def scalar(value: int | str) -> object:
        return _scalar(value, boxed=boxed_scalars)

    with h5py.File(path, "w") as f:
        f.create_dataset("exchange/data", data=np.zeros((projections, 4, 4), dtype=np.uint16))
        if flats is not None:
            f.create_dataset("exchange/data_white", data=np.zeros((flats, 4, 4), dtype=np.uint16))
        if darks is not None:
            f.create_dataset("exchange/data_dark", data=np.zeros((darks, 4, 4), dtype=np.uint16))
        if theta:
            f.create_dataset("exchange/theta", data=np.linspace(0.0, 180.0, projections))
        if num_angles is not None:
            f.create_dataset("process/acquisition/rotation/num_angles", data=scalar(num_angles))
        if num_flat_fields is not None:
            f.create_dataset(
                "process/acquisition/flat_fields/num_flat_fields", data=scalar(num_flat_fields)
            )
        if flat_mode is not None:
            f.create_dataset(
                "process/acquisition/flat_fields/flat_field_mode", data=scalar(flat_mode)
            )
        if num_dark_fields is not None:
            f.create_dataset(
                "process/acquisition/dark_fields/num_dark_fields", data=scalar(num_dark_fields)
            )
        if dark_mode is not None:
            f.create_dataset(
                "process/acquisition/dark_fields/dark_field_mode", data=scalar(dark_mode)
            )
        if start_date is not None:
            f.create_dataset("process/acquisition/start_date", data=scalar(start_date))
        if end_date is not None:
            f.create_dataset("process/acquisition/end_date", data=scalar(end_date))


def _reader(tmp_path: Path, captured_at_source: str = "start_date") -> DataExchangeScanReader:
    return DataExchangeScanReader(
        allowed_roots=(str(tmp_path),), captured_at_source=captured_at_source
    )


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


async def test_describe_one_element_array_scalars_read_the_same_as_zero_d(tmp_path: Path) -> None:
    """The shape 2-BM actually writes.

    Measured on a real scan file: `/process/acquisition` scalars are
    1-element arrays, and NumPy 2 refuses `int()` on those. Before the
    reader handled them, every commanded count came back None at the
    beamline while this whole module stayed green, because the fixture
    only ever wrote the 0-dimensional shape.
    """
    scan = tmp_path / "scan_boxed.h5"
    _write_scan(scan, boxed_scalars=True)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count == 5
    assert result.commanded_flat_count == 2
    assert result.commanded_dark_count == 2
    assert result.dropped_frame_count == 0
    assert result.captured_at_raw == "2026-07-29T10:15:30-05:00"


async def test_describe_boxed_shortfall_reports_the_dropped_frames(tmp_path: Path) -> None:
    scan = tmp_path / "scan_boxed_short.h5"
    _write_scan(scan, projections=3, num_angles=5, boxed_scalars=True)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count == 5
    assert result.dropped_frame_count == 2


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        pytest.param("1501", 1501, id="text_scalar"),
        pytest.param(["1501"], 1501, id="text_in_a_one_element_array"),
    ],
)
async def test_describe_reads_a_commanded_count_written_as_text(
    tmp_path: Path, written: object, expected: int
) -> None:
    """h5py hands string datasets back as bytes.

    A writer that stores a count as text is not a shape this beamline
    uses today, but the reader already decodes bytes for the timestamp
    and the same value can arrive on either path; a count it could
    decode but silently dropped would be the `_scalar_int` bug again in
    a different costume.
    """
    scan = tmp_path / "scan_text_count.h5"
    _write_scan(scan, projections=1501)
    with h5py.File(scan, "a") as f:
        del f["process/acquisition/rotation/num_angles"]
        f.create_dataset("process/acquisition/rotation/num_angles", data=written)

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count == expected


async def test_describe_uncountable_commanded_value_reads_none(tmp_path: Path) -> None:
    """A value that is neither a number nor a sized thing.

    The reader's contract is never to raise, so an unreadable count
    reports unknowable rather than propagating out of the worker
    thread as a failed describe.
    """
    scan = tmp_path / "scan_nan_count.h5"
    _write_scan(scan)
    with h5py.File(scan, "a") as f:
        del f["process/acquisition/rotation/num_angles"]
        f.create_dataset("process/acquisition/rotation/num_angles", data=float("nan"))

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count is None
    assert result.dropped_frame_count is None


async def test_describe_multi_element_array_where_a_scalar_belongs_reads_none(
    tmp_path: Path,
) -> None:
    """A longer array is not a scalar written oddly.

    Reporting its first element would fabricate a commanded count from
    a dataset whose meaning the reader does not know.
    """
    scan = tmp_path / "scan_multi.h5"
    _write_scan(scan)
    with h5py.File(scan, "a") as f:
        del f["process/acquisition/rotation/num_angles"]
        f.create_dataset("process/acquisition/rotation/num_angles", data=[5, 6, 7])

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.commanded_projection_count is None
    assert result.dropped_frame_count is None


async def test_describe_reads_the_declared_timestamp_not_the_first_one(tmp_path: Path) -> None:
    """The 2-BM case, reproduced in miniature.

    A file whose start_date belongs to the previous scan and whose
    end_date is its own. A deployment declaring end_date gets the right
    instant, and the Description says which fact it used so a reader of
    the record never has to assume.
    """
    scan = tmp_path / "scan_two_stamps.h5"
    _write_scan(
        scan,
        start_date="2026-08-11T18:51:06-05:00",
        end_date="2026-08-12T06:21:17-05:00",
    )

    from_start = await _reader(tmp_path).describe(locator_uri=scan.as_uri())
    from_end = await _reader(tmp_path, "end_date").describe(locator_uri=scan.as_uri())

    assert isinstance(from_start, Description)
    assert isinstance(from_end, Description)
    assert from_start.captured_at_raw == "2026-08-11T18:51:06-05:00"
    assert from_start.captured_at_source == "start_date"
    assert from_end.captured_at_raw == "2026-08-12T06:21:17-05:00"
    assert from_end.captured_at_source == "end_date"


async def test_describe_declared_timestamp_absent_reads_none_not_the_other_one(
    tmp_path: Path,
) -> None:
    """No silent fallback.

    A deployment that declared end_date and got a file without one has
    a broken assumption, and the ingest refusing is how it finds out.
    Falling back to start_date would hand back the exact wrong value
    the declaration exists to avoid.
    """
    scan = tmp_path / "scan_no_end.h5"
    _write_scan(scan, start_date="2026-08-11T18:51:06-05:00", end_date=None)

    result = await _reader(tmp_path, "end_date").describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.captured_at is None
    assert result.captured_at_raw is None
    assert result.captured_at_source == "end_date"


def test_reader_refuses_a_timestamp_the_layout_does_not_offer() -> None:
    with pytest.raises(ValueError, match="not a timestamp this layout offers"):
        DataExchangeScanReader(allowed_roots=("/tmp",), captured_at_source="acquired_on")


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
    assert result.captured_at is not None
    assert result.captured_at.utcoffset() is not None
    assert result.captured_at_raw == "2026-07-29T10:15:30-05:00"


async def test_describe_naive_start_date_stays_raw(tmp_path: Path) -> None:
    """A naive string must not be assigned a zone; the site timezone
    rule is an open staff question."""
    scan = tmp_path / "scan_008.h5"
    _write_scan(scan, start_date="2026-07-29T10:15:30")

    result = await _reader(tmp_path).describe(locator_uri=scan.as_uri())

    assert isinstance(result, Description)
    assert result.captured_at is None
    assert result.captured_at_raw == "2026-07-29T10:15:30"


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


_PERSONAL_PATH_FRAGMENT = "Smith-1015116"


async def test_describe_missing_file_reason_never_carries_the_path(tmp_path: Path) -> None:
    """A missing file's `os.stat` raises `FileNotFoundError`, whose
    `str()` renders its own path -- and 2-BM's directory layout embeds a
    PI surname in exactly that path. The reason must carry the
    exception TYPE, never its message."""
    root = tmp_path / _PERSONAL_PATH_FRAGMENT
    root.mkdir()
    missing = root / "scan.h5"

    result = await _reader(tmp_path).describe(locator_uri=missing.as_uri())

    assert isinstance(result, Unreadable)
    assert _PERSONAL_PATH_FRAGMENT not in result.reason
    assert "FileNotFoundError" in result.reason


async def test_describe_non_hdf5_bytes_reason_never_carries_the_path(tmp_path: Path) -> None:
    root = tmp_path / _PERSONAL_PATH_FRAGMENT
    root.mkdir()
    bogus = root / "scan.h5"
    bogus.write_bytes(b"this is not an HDF5 file")

    result = await _reader(tmp_path).describe(locator_uri=bogus.as_uri())

    assert isinstance(result, Unreadable)
    assert _PERSONAL_PATH_FRAGMENT not in result.reason
    assert "OSError" in result.reason
