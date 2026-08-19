"""`ChecksumComputer` over SSH: digest a file on a remote host.

Slice 17's transport adapter, sibling to `SshDataExchangeScanReader`. Runs
the SAME `PosixChecksumAdapter.compute` used locally, unchanged, inside
`cora.data._remote_scan_probe` on `config.host`. Implements only
`ChecksumComputer` (ingest's first-time digest), not `ChecksumVerifier`:
`record_attestation`'s re-verify path is a different flow with no
measured need to run remotely yet, and adding the second protocol here
before a trigger fires would be the rule-of-three's mistake.

A SEPARATE `run_probe` call from `SshDataExchangeScanReader.describe`,
deliberately: `ingest_scan/handler.py`'s changed-under-read guard compares
the two adapters' independent stat snapshots, and collapsing both probes
into one remote round trip would make that guard agree by construction --
see the independent-check principle. Two SSH round trips per ingest is
the cost of keeping it real.

`kind = "SshPosixChecksum"`, distinct from the local
`PosixChecksumAdapter.kind = "PosixChecksum"`, mirroring
`SshDataExchangeScanReader`'s naming.

Never logs `locator_uri`: it is the same personal-data value
`run.aggregates.run.capture_path` vaults rather than logs (2-BM's
directory layout embeds a surname and proposal number), and this
adapter has no more right to it in a log line than that module does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.data.adapters._ssh_probe import SshProbeConfig, run_probe
from cora.data.ports.checksum_computer import ChecksumComputationResult, ComputedChecksum
from cora.data.ports.checksum_verifier import Unreachable
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

_log = get_logger(__name__)


class SshPosixChecksumComputer:
    """`ChecksumComputer` that digests a file on a remote host."""

    kind = "SshPosixChecksum"

    def __init__(self, *, config: SshProbeConfig) -> None:
        self._config = config

    async def compute(
        self,
        *,
        locator_uri: str,
        supply_id: UUID,
    ) -> ChecksumComputationResult:
        response = await run_probe(
            {"op": "checksum", "locator_uri": locator_uri, "supply_id": str(supply_id)},
            config=self._config,
        )
        result = _response_to_result(response)
        if isinstance(result, Unreachable):
            _log.warning(
                "ssh_posix_checksum_computer.compute_failed",
                supply_id=str(supply_id),
                host=self._config.host,
                error_detail=result.error_detail,
            )
        return result


def _response_to_result(response: dict[str, object]) -> ChecksumComputationResult:
    if response.get("kind") == "ComputedChecksum":
        try:
            return ComputedChecksum(
                algorithm=str(response["algorithm"]),
                value=str(response["value"]),
                byte_size=int(response["byte_size"]),  # type: ignore[arg-type]
                mtime_ns=int(response["mtime_ns"]),  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            # A probe-version skew must read as Unreachable, not a 500;
            # see the sibling reader's identical reasoning.
            return Unreachable(error_detail=f"malformed probe response: {exc}")
    # "Unreachable", "ProbeError", or any unparseable response: fail
    # toward Unreachable, matching the port's never-raise contract.
    detail = (
        response.get("error_detail")
        or response.get("detail")
        or f"unexpected response: {response!r}"
    )
    return Unreachable(error_detail=str(detail))


__all__ = ["SshPosixChecksumComputer"]
