"""POSIX (``file://``) adapter implementing ``ChecksumVerifier``.

Reads the bytes at a ``file://`` Distribution URI from a local or mounted
filesystem and feeds sha256 in chunks. Used where CORA's host actually
mounts the storage holding the authoritative copy (the operator opts in by
configuring ``posix_checksum_roots``).

## Root-gating (why this is safe to point at operator-supplied URIs)

A Distribution URI is operator-asserted, so an unbounded reader would be a
local-file-read primitive. The adapter is constructed with an allowlist of
absolute filesystem roots and refuses any path whose RESOLVED realpath is
not contained by one of them. ``os.path.realpath`` collapses ``..`` segments
and follows symlinks before the containment check, so neither path traversal
nor a symlink planted under a root that points outside it can escape the
sandbox. An empty allowlist refuses every path (the feature is off).

## Network failure policy

Mirrors ``HttpRangeChecksumAdapter``: the port contract is that ``verify``
never raises on an I/O or safety failure. A missing file, a directory, a
permission error, a path outside the roots, an over-budget walk, or a
non-``file`` URI all return ``Unreachable(error_detail=...)``; the recorded
fact IS the ``Unreachable`` outcome.

## Why chunked + offloaded

Distribution byte-sizes range from KiB to many GiB. Reading the whole file
into memory before hashing is unsafe at the big end, so the walk reads in
1 MiB chunks. All filesystem work (realpath resolution, the containment
check, and the read+hash) runs in a worker thread via ``asyncio.to_thread``
so it never blocks the event loop.
"""

import asyncio
import hashlib
import os
import time
from urllib.parse import unquote, urlparse
from uuid import UUID

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
    """``ChecksumVerifier`` over local / mounted files via ``file://`` URIs."""

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
        # resolves here, not on every verify).
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
        parsed = urlparse(distribution_uri)
        if parsed.scheme != "file":
            return Unreachable(error_detail=f"not a file URI: scheme {parsed.scheme!r}")
        if parsed.netloc not in ("", "localhost"):
            return Unreachable(error_detail=f"file URI names a remote host {parsed.netloc!r}")
        raw_path = unquote(parsed.path)
        if not raw_path:
            return Unreachable(error_detail="file URI has empty path")

        try:
            return await asyncio.to_thread(
                self._resolve_and_hash,
                raw_path,
                expected_checksum,
                distribution_uri,
                supply_id,
            )
        except (OSError, ValueError) as exc:
            # ValueError covers an embedded null byte in the decoded path
            # (a URI like file:///x%00y is fully printable yet decodes to a
            # null path that os.path.realpath / open reject). The port
            # contract is never-raise: surface it as Unreachable, not a 500.
            _log.warning(
                "posix_checksum.read_failed",
                distribution_uri=distribution_uri,
                supply_id=str(supply_id),
                error=str(exc),
            )
            return Unreachable(error_detail=f"read failed: {exc}")

    def _resolve_and_hash(
        self,
        raw_path: str,
        expected_checksum: str,
        distribution_uri: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        """Resolve, root-check, and hash the file. Runs in a worker thread."""
        real_path = os.path.realpath(raw_path)
        if not self._is_within_allowed_roots(real_path):
            _log.warning(
                "posix_checksum.path_outside_roots",
                distribution_uri=distribution_uri,
                supply_id=str(supply_id),
                resolved_path=real_path,
            )
            return Unreachable(error_detail="resolved path is outside the allowed roots")

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
        computed = hasher.hexdigest()
        if computed == expected_checksum:
            return Match(computed_checksum=computed)
        return Mismatch(computed_checksum=computed)

    def _is_within_allowed_roots(self, real_path: str) -> bool:
        for root in self._allowed_roots:
            try:
                if os.path.commonpath([real_path, root]) == root:
                    return True
            except ValueError:
                # Mixed absolute/relative or (on other platforms) different
                # drives: not contained.
                continue
        return False


__all__ = ["PosixChecksumAdapter"]
