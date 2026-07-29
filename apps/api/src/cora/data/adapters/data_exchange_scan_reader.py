"""Data Exchange (``file://`` HDF5) adapter implementing ``ScanReader``.

Reads the facts out of one tomoscan-written Data Exchange scan file:
frame roles from the ``/exchange`` datasets, commanded counts from the
``/process/acquisition`` groups the areaDetector layout writes, the
acquisition timestamp, and a stat snapshot for the live-file guard.
Format vocabulary (every dataset path below) dies here; only roles,
counts, angles, and timestamps cross the port.

## The read set, and who authors it

The file has two authors. tomoscan writes ``/exchange`` (the image
stacks, and ``theta`` in a post-capture append); the areaDetector
layout XML configured in the detector IOC writes ``/process`` and
``/defaults``. The commanded-geometry datasets
(``rotation/num_angles``, the flat and dark mode-and-count groups) are
written on clean file close, so a crashed file lacks them and the
commanded counts honestly read None; ``start_date`` is written on file
open, so a crashed file keeps its timestamp. Flat and dark expected
counts use tomoscan's own arithmetic: the configured count times the
number of phases the mode names (Start or End contribute one each,
Both contributes two, None contributes zero).

## Locking, and why it is not optional

The file is opened read-only with HDF5 file locking disabled. Two
independent reasons: HDF5's flock is unreliable-to-fatal on network
filesystems, which is exactly where the analysis tier lives; and a
reader HOLDING a shared lock can make tomoscan's own post-capture
``add_theta`` append reopen fail, a failure tomoscan swallows, so
observation would silently break the pipeline it observes. SWMR is
not attempted: the writer never opts in, and the reader must stay
safe against files still being written, which is what the
stat-snapshot guard and the never-raise contract are for.

libhdf5 is not thread-safe and h5py serializes all API calls behind
one lock, so each describe runs as a single open-read-close unit in a
worker thread; reads serialize per process and never block the event
loop.

## Structural completeness is not finality

``/exchange/theta`` present means post-processing COMPLETED. Its
absence means only that post-processing has not completed: not yet
run, failed permanently (tomoscan wraps ``add_theta`` in a bare
except and proceeds), or a scan that produced zero projections.
Deciding whether the file will still CHANGE is the finality axis, a
deployment protocol that lives outside this adapter.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import os
from datetime import datetime
from typing import Any

import h5py

from cora.data.adapters._file_uri import Refused, resolve_confined_file_uri
from cora.data.ports.scan_reader import (
    Description,
    ScanReadResult,
    Unreadable,
    Unrecognized,
)
from cora.infrastructure.logging import get_logger

_log = get_logger(__name__)

_MEDIA_TYPE = "application/x-hdf5"

_DATA = "exchange/data"
_DATA_WHITE = "exchange/data_white"
_DATA_DARK = "exchange/data_dark"
_THETA = "exchange/theta"
_THETA_WHITE = "exchange/theta_white"
_THETA_DARK = "exchange/theta_dark"
_START_DATE = "process/acquisition/start_date"
_NUM_ANGLES = "process/acquisition/rotation/num_angles"
_NUM_FLAT_FIELDS = "process/acquisition/flat_fields/num_flat_fields"
_FLAT_FIELD_MODE = "process/acquisition/flat_fields/flat_field_mode"
_NUM_DARK_FIELDS = "process/acquisition/dark_fields/num_dark_fields"
_DARK_FIELD_MODE = "process/acquisition/dark_fields/dark_field_mode"


class DataExchangeScanReader:
    """``ScanReader`` over tomoscan-written Data Exchange HDF5 files."""

    kind = "DataExchange"

    def __init__(self, *, allowed_roots: tuple[str, ...]) -> None:
        # Same canonicalisation as PosixChecksumAdapter: roots resolve
        # once so containment compares realpath-to-realpath.
        self._allowed_roots = tuple(os.path.realpath(root) for root in allowed_roots)

    async def describe(self, *, locator_uri: str) -> ScanReadResult:
        try:
            return await asyncio.to_thread(self._describe_sync, locator_uri)
        except Exception as exc:
            # h5py surfaces malformed files as a zoo of exception types
            # (OSError, KeyError, RuntimeError from libhdf5); the port
            # contract is that a bad FILE is a result, not a 500.
            _log.warning(
                "data_exchange_scan_reader.read_failed",
                locator_uri=locator_uri,
                error=str(exc),
            )
            return Unreadable(reason=f"read failed: {exc}")

    def _describe_sync(self, locator_uri: str) -> ScanReadResult:
        resolved = resolve_confined_file_uri(locator_uri, self._allowed_roots)
        if isinstance(resolved, Refused):
            _log.warning(
                "data_exchange_scan_reader.refused",
                locator_uri=locator_uri,
                reason=resolved.reason,
            )
            return Unreadable(reason=resolved.reason)
        real_path = resolved.real_path

        # Snapshot BEFORE the structural read; the digest pass re-stats
        # after its walk and the ingest handler refuses on a difference.
        try:
            stat = os.stat(real_path)
        except OSError as exc:
            return Unreadable(reason=f"stat failed: {exc}")

        try:
            handle = h5py.File(real_path, "r", locking=False)
        except OSError as exc:
            return Unreadable(reason=f"not readable as HDF5: {exc}")

        with handle:
            data = _dataset(handle, _DATA)
            if data is None:
                # The one dataset the Data Exchange spec makes mandatory.
                # Anything else absent is a count of zero, not a verdict.
                return Unrecognized(reason="no /exchange/data dataset")

            projection_count = _frame_count(data)
            flat_count = _optional_frame_count(handle, _DATA_WHITE)
            dark_count = _optional_frame_count(handle, _DATA_DARK)

            projection_angles = _angles(handle, _THETA)
            flat_angles = _angles(handle, _THETA_WHITE)
            dark_angles = _angles(handle, _THETA_DARK)

            commanded_projections = _scalar_int(handle, _NUM_ANGLES)
            commanded_flats = _phase_count(
                _scalar_int(handle, _NUM_FLAT_FIELDS),
                _scalar_str(handle, _FLAT_FIELD_MODE),
            )
            commanded_darks = _phase_count(
                _scalar_int(handle, _NUM_DARK_FIELDS),
                _scalar_str(handle, _DARK_FIELD_MODE),
            )

            start_date_raw = _scalar_str(handle, _START_DATE)

        dropped: int | None = None
        if commanded_projections is not None:
            shortfall = commanded_projections - projection_count
            # A negative shortfall means the source contradicts itself
            # (more captured than commanded); report unknowable rather
            # than a fabricated negative.
            dropped = shortfall if shortfall >= 0 else None

        return Description(
            media_type=_MEDIA_TYPE,
            structurally_complete=projection_angles is not None,
            projection_count=projection_count,
            flat_count=flat_count,
            dark_count=dark_count,
            # Data Exchange has no per-frame invalid marking; 0 means
            # none-marked, not all-validated (NXtomo image_key=3 is the
            # role's producing format).
            invalid_count=0,
            commanded_projection_count=commanded_projections,
            commanded_flat_count=commanded_flats,
            commanded_dark_count=commanded_darks,
            dropped_frame_count=dropped,
            projection_angles_deg=projection_angles,
            flat_angles_deg=flat_angles,
            dark_angles_deg=dark_angles,
            start_date=_parse_aware(start_date_raw),
            start_date_raw=start_date_raw,
            byte_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )


def _dataset(handle: h5py.File, path: str) -> Any | None:
    node = handle.get(path)
    return node if isinstance(node, h5py.Dataset) else None


def _frame_count(dataset: Any) -> int:
    shape = getattr(dataset, "shape", ())
    return int(shape[0]) if len(shape) >= 1 else 0


def _optional_frame_count(handle: h5py.File, path: str) -> int:
    dataset = _dataset(handle, path)
    return _frame_count(dataset) if dataset is not None else 0


def _angles(handle: h5py.File, path: str) -> tuple[float, ...] | None:
    dataset = _dataset(handle, path)
    if dataset is None:
        return None
    try:
        values = dataset[()]
        return tuple(float(value) for value in values)
    except (TypeError, ValueError, OSError):
        # A scalar or unreadable theta is not an angle list; report the
        # dataset as absent rather than fabricate a shape for it. For
        # /exchange/theta that also reads as structurally incomplete,
        # which is the honest verdict for a malformed one.
        return None


def _scalar_int(handle: h5py.File, path: str) -> int | None:
    dataset = _dataset(handle, path)
    if dataset is None:
        return None
    try:
        value = dataset[()]
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        return int(value)
    except (TypeError, ValueError, OSError):
        return None


def _scalar_str(handle: h5py.File, path: str) -> str | None:
    dataset = _dataset(handle, path)
    if dataset is None:
        return None
    try:
        value = dataset[()]
    except OSError:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    # Some writers store scalar strings as 1-element arrays.
    try:
        first = value[0]
    except (TypeError, IndexError, KeyError):
        return None
    if isinstance(first, bytes):
        return first.decode("utf-8", errors="replace")
    return str(first) if isinstance(first, str) else None


def _phase_count(configured: int | None, mode: str | None) -> int | None:
    """Expected-count arithmetic per tomoscan: configured count times
    the phases the mode names. Unknown mode strings read as unknowable,
    not zero, so a new tomoscan mode cannot silently claim nothing was
    commanded."""
    if configured is None or mode is None:
        return None
    if mode not in ("Start", "End", "Both", "None"):
        return None
    phases = (mode in ("Start", "Both")) + (mode in ("End", "Both"))
    return configured * phases


def _parse_aware(raw: str | None) -> datetime | None:
    """Parse a timestamp string ONLY when it is timezone-aware.

    A naive string stays unparsed: assigning it a zone would
    manufacture provenance, and the site's timezone rule is an open
    staff question that lands here once answered.
    """
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


__all__ = ["DataExchangeScanReader"]
