"""HTTP / HTTPS adapter implementing ``ChecksumVerifier``.

Walks the bytes at the Distribution URI by issuing a HEAD then a
sequence of ``Range`` GETs (1 MiB chunks) feeding sha256. Honors a
configurable ``max_walk_seconds`` timeout that converts to
``Unreachable`` on overrun.

## Network failure policy

Any transport-layer failure (timeout, 4xx/5xx, malformed Content-Length,
DNS error, TLS handshake failure) returns ``Unreachable(error_detail=...)``
rather than raising. The handler's contract per
[[project_data_attestation_design]] L15 step 14 is that verifier-port
calls do not raise on transient errors; the recorded fact IS the
``Unreachable`` outcome.

## Why range-read in 1 MiB chunks

Distribution byte-sizes range from KiB (calibration scans) to many
GiB (large stitch reconstructions). Buffering the whole response in
memory before hashing is unsafe for the big-end of that range.
Range-reads cap the memory footprint regardless of file size; 1 MiB
is a reasonable balance between request overhead and memory bound.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import hashlib
import time
from uuid import UUID

import httpx

from cora.data.ports.checksum_verifier import (
    ChecksumVerificationResult,
    Match,
    Mismatch,
    Unreachable,
)
from cora.infrastructure.logging import get_logger

_log = get_logger(__name__)

#: Default per-chunk size. 1 MiB.
_DEFAULT_CHUNK_BYTES = 1024 * 1024

#: Default end-to-end walk budget. 60 s tops; operators can tune the
#: adapter at construction time for long-tail GiB files.
_DEFAULT_MAX_WALK_SECONDS = 60.0


class HttpRangeChecksumAdapter:
    """``ChecksumVerifier`` over HTTP / HTTPS via range-read sha256."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        chunk_bytes: int = _DEFAULT_CHUNK_BYTES,
        max_walk_seconds: float = _DEFAULT_MAX_WALK_SECONDS,
    ) -> None:
        self._client = client
        self._chunk_bytes = chunk_bytes
        self._max_walk_seconds = max_walk_seconds

    async def verify(
        self,
        *,
        distribution_uri: str,
        expected_checksum: str,
        supply_id: UUID,
    ) -> ChecksumVerificationResult:
        deadline = time.monotonic() + self._max_walk_seconds
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            try:
                head = await client.head(distribution_uri, follow_redirects=True)
            except httpx.HTTPError as exc:
                _log.warning(
                    "http_range_checksum.head_failed",
                    distribution_uri=distribution_uri,
                    supply_id=str(supply_id),
                    error=str(exc),
                )
                return Unreachable(error_detail=f"HEAD failed: {exc}")
            if head.status_code >= 400:
                return Unreachable(error_detail=f"HEAD returned status {head.status_code}")
            content_length_raw = head.headers.get("Content-Length")
            if content_length_raw is None:
                return Unreachable(error_detail="HEAD missing Content-Length")
            try:
                total_bytes = int(content_length_raw)
            except ValueError:
                return Unreachable(
                    error_detail=f"HEAD Content-Length not an integer: {content_length_raw!r}"
                )
            if total_bytes < 0:
                return Unreachable(error_detail=f"HEAD Content-Length negative: {total_bytes}")
            hasher = hashlib.sha256()
            offset = 0
            while offset < total_bytes:
                if time.monotonic() > deadline:
                    return Unreachable(
                        error_detail=(f"walk exceeded max_walk_seconds={self._max_walk_seconds}")
                    )
                end = min(offset + self._chunk_bytes, total_bytes) - 1
                range_header = f"bytes={offset}-{end}"
                try:
                    chunk = await client.get(
                        distribution_uri,
                        headers={"Range": range_header},
                        follow_redirects=True,
                    )
                except httpx.HTTPError as exc:
                    _log.warning(
                        "http_range_checksum.range_failed",
                        distribution_uri=distribution_uri,
                        supply_id=str(supply_id),
                        range=range_header,
                        error=str(exc),
                    )
                    return Unreachable(error_detail=f"GET {range_header} failed: {exc}")
                if chunk.status_code not in (200, 206):
                    return Unreachable(
                        error_detail=(f"GET {range_header} returned status {chunk.status_code}")
                    )
                body = chunk.content
                if not body:
                    return Unreachable(error_detail=f"GET {range_header} returned empty body")
                hasher.update(body)
                offset += len(body)
            computed = hasher.hexdigest()
            if computed == expected_checksum:
                return Match(computed_checksum=computed)
            return Mismatch(computed_checksum=computed)
        finally:
            if owns_client:
                await client.aclose()


__all__ = ["HttpRangeChecksumAdapter"]
