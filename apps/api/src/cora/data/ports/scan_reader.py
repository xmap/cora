"""ScanReader: Data BC's port for reading facts out of a scan file.

Used by the ``ingest_scan`` handler to turn one on-disk scan product
into the facts the Data BC's registration commands need: frame roles
and counts, angles, structural completeness, the acquisition
timestamp, and a stat snapshot. The port encapsulates the layout
(Data Exchange today, NeXus NXtomo when a deployment selects it); the
domain never sees a dataset path.

## The axis map

Scan ingest separates four independently varying concerns, and this
port is exactly one of them:

  - layout (THIS PORT): how facts are read out of the file;
  - finality: when the file stops changing (a deployment protocol,
    not a file property; two beamlines writing the same layout can
    differ);
  - correlation: whose experiment the file belongs to (a scheduling
    derivation, not a file property);
  - transport: how CORA reaches the bytes (the locator's meaning).

Fusing any of the other three into an adapter here is the mistake the
seam exists to prevent.

## Roles, not paths

The payload speaks a closed frame-role vocabulary
{projection, flat, dark, invalid}. Data Exchange separates roles into
datasets (``/exchange/data`` + ``data_white`` + ``data_dark``); NXtomo
interleaves one stack tagged per-frame by ``image_key`` (0 projection,
1 flat, 2 dark, 3 invalid). Counts absorb both shapes; paths absorb
neither, which is why the payload carries no paths.

``invalid_count`` counts frames the layout MARKS unusable. A layout
with no marking (Data Exchange) reports 0, meaning none-marked, not
all-validated.

## Zero versus None on counts

0 means verified-none; None means the source cannot know. A crashed
Data Exchange file has no commanded counts (they are written on clean
close), and NXtomo has no commanded counts at all, so
``dropped_frame_count`` and the ``commanded_*`` fields are optional
rather than defaulted, and a consumer must not read absence as zero.

## Discriminated result

``Description | Unreadable | Unrecognized``, bare variant names scoped
by this module per the ChecksumVerifier precedent
(``Match | Mismatch | Unreachable``). ``Unrecognized`` fires only when
the one dataset the layout makes mandatory is absent; a missing or
empty ROLE dataset is count 0, never Unrecognized (a no-flats scan is
a designed acquisition mode, not a malformed file). ``Unreadable`` may
be transient: a half-transferred file on the analysis tier is an
expected observable, and the caller decides whether to retry.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Description:
    """The facts one readable scan file yields.

    ``byte_size`` and ``mtime_ns`` are the stat snapshot taken before
    the structural read; the ingest handler compares them against the
    digest pass's snapshot to refuse files that changed while being
    read (the live-file guard).

    ``start_date`` is parsed ONLY when the file's timestamp string
    carries an unambiguous offset; a naive string stays raw in
    ``start_date_raw`` with ``start_date=None``, because guessing a
    timezone would manufacture provenance. The site timezone rule, once
    staff confirm it, lands in the adapter and turns those raws into
    parsed values.
    """

    media_type: str
    structurally_complete: bool
    projection_count: int
    flat_count: int
    dark_count: int
    invalid_count: int
    commanded_projection_count: int | None
    commanded_flat_count: int | None
    commanded_dark_count: int | None
    dropped_frame_count: int | None
    projection_angles_deg: tuple[float, ...] | None
    flat_angles_deg: tuple[float, ...] | None
    dark_angles_deg: tuple[float, ...] | None
    start_date: datetime | None
    start_date_raw: str | None
    byte_size: int
    mtime_ns: int


@dataclass(frozen=True)
class Unreadable:
    """The bytes could not be opened or walked (I/O failure, not a
    layout verdict). Possibly transient; carries the reason."""

    reason: str


@dataclass(frozen=True)
class Unrecognized:
    """Readable, but the layout's one mandatory dataset is absent, so
    this is not a file the adapter's layout describes."""

    reason: str


ScanReadResult = Description | Unreadable | Unrecognized


class ScanReader(Protocol):
    """Data BC port: read the registration facts out of one scan file."""

    kind: str
    """Short adapter-kind label stamped into the recorded evidence as
    ``reader_kind``. Forensic provenance: records WHICH layout reader
    produced the facts. A class attribute on each adapter."""

    async def describe(self, *, locator_uri: str) -> ScanReadResult:
        """Read the facts at ``locator_uri`` without writing anything.

        The locator is opaque to callers and interpreted by the
        adapter (one-file-one-scan is a 2-BM property, not a port
        property; a future layout may address an entry inside a
        file). Implementations MUST open read-only without taking
        filesystem locks, MUST NOT raise on I/O or layout failures
        (return ``Unreadable`` / ``Unrecognized``), and MUST be safe
        to point at a file another process is still writing.
        """
        ...


class ConfiguredScanReader:
    """Test stub: returns a per-locator configured result.

    Construct with ``{locator_uri: result}``; unmapped locators raise
    ``KeyError`` (loud surface for test misconfiguration).
    """

    kind = "Configured"

    def __init__(self, configured_results: dict[str, ScanReadResult]) -> None:
        self._configured = dict(configured_results)

    async def describe(self, *, locator_uri: str) -> ScanReadResult:
        return self._configured[locator_uri]


__all__ = [
    "ConfiguredScanReader",
    "Description",
    "ScanReadResult",
    "ScanReader",
    "Unreadable",
    "Unrecognized",
]
