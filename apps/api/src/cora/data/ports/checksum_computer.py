"""ChecksumComputer: first-time digest production for ingest.

``ChecksumVerifier`` answers "do these bytes still match the recorded
digest?", so its contract requires an ``expected_checksum`` input. An
ingest has no prior record: the digest is its OUTPUT, feeding
``RegisterDataset.checksum_value``. Reusing the verifier would mean
calling ``verify`` with a sentinel and reading the digest off
``Mismatch``, which inverts the port's semantics; this sibling port
carries the compute-first-time contract instead.

Same family as ``ChecksumVerifier`` (its ``Unreachable`` variant is
reused rather than duplicated), and the production adapter is the same
class: ``PosixChecksumAdapter`` implements both protocols over one
root-confined resolve-and-hash core.

## The stat snapshot

``ComputedChecksum`` carries the file's size and mtime observed AFTER
the hash walk. The ingest handler compares them with the snapshot the
``ScanReader`` took BEFORE its structural read; a difference means the
file changed while being described, and the ingest refuses rather
than record facts and digest from two different files that happened to
share a path (the live-file guard).
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.data.ports.checksum_verifier import Unreachable


@dataclass(frozen=True)
class ComputedChecksum:
    """A digest produced over the bytes at a locator, plus the stat
    snapshot taken after the walk."""

    algorithm: str
    value: str
    byte_size: int
    mtime_ns: int


ChecksumComputationResult = ComputedChecksum | Unreachable


class ChecksumComputer(Protocol):
    """Data BC port: produce a digest for bytes with no prior record."""

    kind: str
    """Adapter-kind label for evidence provenance, mirroring
    ``ChecksumVerifier.kind``."""

    async def compute(
        self,
        *,
        locator_uri: str,
        supply_id: UUID,
    ) -> ChecksumComputationResult:
        """Walk the bytes at ``locator_uri`` and return their digest.

        Same never-raise contract as ``ChecksumVerifier.verify``: any
        I/O or confinement failure returns ``Unreachable``.
        ``supply_id`` is forensic logging context, as on ``verify``.
        """
        ...


class ConfiguredChecksumComputer:
    """Test stub: returns a per-locator configured result.

    Construct with ``{locator_uri: result}``; unmapped locators raise
    ``KeyError`` (loud surface for test misconfiguration).
    """

    kind = "Configured"

    def __init__(self, configured_results: dict[str, ChecksumComputationResult]) -> None:
        self._configured = dict(configured_results)

    async def compute(
        self,
        *,
        locator_uri: str,
        supply_id: UUID,
    ) -> ChecksumComputationResult:
        _ = supply_id
        return self._configured[locator_uri]


__all__ = [
    "ChecksumComputationResult",
    "ChecksumComputer",
    "ComputedChecksum",
    "ConfiguredChecksumComputer",
]
