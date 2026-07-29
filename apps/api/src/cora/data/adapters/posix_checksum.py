"""POSIX (``file://``) adapter for both checksum ports.

Reads the bytes at a ``file://`` URI from a local or mounted filesystem
and feeds sha256 in chunks. One class, two Protocols:

  - ``ChecksumVerifier.verify`` (record_attestation): compute and
    compare against an expected digest.
  - ``ChecksumComputer.compute`` (ingest_scan): compute a first-time
    digest for bytes with no prior record, returning the digest plus
    an after-walk stat snapshot for the live-file guard.

Both run the same root-confined resolve-and-hash core, so the safety
rule cannot drift between them. Used where CORA's host actually mounts
the storage holding the authoritative copy (the operator opts in by
configuring ``posix_checksum_roots``).

## Root-gating (why this is safe to point at operator-supplied URIs)

A URI reaching either method is operator-asserted, so an unbounded
reader would be a local-file-read primitive. Resolution + containment
live in ``cora.data.adapters._file_uri`` (shared with the scan
reader): the RESOLVED realpath must sit inside an allowlisted root,
which defeats both ``..`` traversal and planted symlinks. An empty
allowlist refuses every path (the feature is off).

## Network failure policy

Mirrors ``HttpRangeChecksumAdapter``: neither method ever raises on an
I/O or safety failure. A missing file, a directory, a permission
error, a path outside the roots, an over-budget walk, or a non-``file``
URI all return ``Unreachable(error_detail=...)``; the recorded fact IS
the ``Unreachable`` outcome.

## Why chunked + offloaded

Byte-sizes range from KiB to many GiB. Reading the whole file into
memory before hashing is unsafe at the big end, so the walk reads in
1 MiB chunks. All filesystem work (realpath resolution, the
containment check, and the read+hash) runs in a worker thread via
``asyncio.to_thread`` so it never blocks the event loop.
"""

import asyncio
import hashlib
import os
import time
from uuid import UUID

from cora.data.adapters._file_uri import Refused, resolve_confined_file_uri
from cora.data.ports.checksum_computer import ChecksumComputationResult, ComputedChecksum
from cora.data.ports.checksum_verifier import (
    ChecksumVerificationResult,
    Match,
    Mismatch,
    Unreachable,
)
from cora.infrastructure.logging import get_logger

_log = get_logger(__name__)

#: Default per-chunk read size. 1 MiB (matches HttpRangeChecksumAdapter).
_DEFAULT_CHUNK_BYTES = 1024 * 1024

#: Default end-to-end walk budget. 60 s; operators tune at construction time
#: for long-tail GiB files.
_DEFAULT_MAX_WALK_SECONDS = 60.0


class PosixChecksumAdapter:
    """Checksum verify + compute over local / mounted ``file://`` URIs."""

    kind = "PosixChecksum"

    def __init__(
        self,
        *,
        allowed_roots: tuple[str, ...],
        chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
        max_walk_seconds: float = _DEFAULT_MAX_WALK_SECONDS,
    ) -> None:
        # Canonicalise the roots once so the per-call containment check
        # compares realpath-to-realpath (a root that is itself a symlink
        # resolves here, not on every call).
        self._allowed_roots = tuple(os.path.realpath(root) for root in allowed_roots)
        self._chunk_bytes = chunk_bytes
        self._max_walk_seconds = max_walk_seconds

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        try:
            return await asyncio.to_thread(
                self._resolve_and_hash,
                distribution_uri,
                expected_checksum,
                supply_id,
            )
        except (OSError, ValueError) as exc:
            _log.warning(
                "posix_checksum.read_failed",
                distribution_uri=distribution_uri,
                supply_id=str(supply_id),
                error=str(exc),
            )
            return Unreachable(error_detail=f"read failed: {exc}")

    async def compute(
        self,
        *,
        locator_uri: str,
        supply_id: UUID,
    ) -> ChecksumComputationResult:
        try:
            return await asyncio.to_thread(self._resolve_and_digest, locator_uri, supply_id)
        except (OSError, ValueError) as exc:
            _log.warning(
                "posix_checksum.compute_failed",
                locator_uri=locator_uri,
                supply_id=str(supply_id),
                error=str(exc),
            )
            return Unreachable(error_detail=f"read failed: {exc}")

    def _resolve_and_hash(
        self,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        """Resolve, root-check, and hash the file. Runs in a worker thread."""
        resolved = resolve_confined_file_uri(distribution_uri, self._allowed_roots)
        if isinstance(resolved, Refused):
            _log.warning(
                "posix_checksum.refused",
                distribution_uri=distribution_uri,
                supply_id=str(supply_id),
                reason=resolved.reason,
            )
            return Unreachable(error_detail=resolved.reason)

        computed = self._hash_file(resolved.real_path)
        if isinstance(computed, Unreachable):
            return computed
        if computed == expected_checksum:
            return Match(computed_checksum=computed)
        return Mismatch(computed_checksum=computed)

    def _resolve_and_digest(
        self,
        locator_uri: str,
        supply_id: UUID,
    ) -> ChecksumComputationResult:
        """Resolve, root-check, hash, and stat the file. Worker thread."""
        resolved = resolve_confined_file_uri(locator_uri, self._allowed_roots)
        if isinstance(resolved, Refused):
            _log.warning(
                "posix_checksum.refused",
                locator_uri=locator_uri,
                supply_id=str(supply_id),
                reason=resolved.reason,
            )
            return Unreachable(error_detail=resolved.reason)

        computed = self._hash_file(resolved.real_path)
        if isinstance(computed, Unreachable):
            return computed
        # Stat AFTER the walk: this snapshot is the second point of the
        # ingest live-file guard (the reader statted before its read).
        stat = os.stat(resolved.real_path)
        return ComputedChecksum(
            algorithm="sha256",
            value=computed,
            byte_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
        )

    def _hash_file(self, real_path: str) -> str | Unreachable:
        deadline = time.monotonic() + self._max_walk_seconds
        hasher = hashlib.sha256()
        with open(real_path, "rb") as handle:
            while True:
                if time.monotonic() > deadline:
                    return Unreachable(
                        error_detail=f"walk exceeded max_walk_seconds={self._max_walk_seconds}"
                    )
                chunk = handle.read(self._chunk_bytes)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()


__all__ = ["PosixChecksumAdapter"]
