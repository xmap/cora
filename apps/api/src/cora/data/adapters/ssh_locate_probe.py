"""`LocateProbe` over SSH: find the durable copy on the host holding it.

Sibling of `SshPosixChecksumComputer` and `SshDataExchangeScanReader`.
`run_locate_probe` (`cora.data.adapters._ssh_probe`) already has exactly
the shape `cora.api._durable_distribution_driver.LocateProbe` declares,
minus the `config` argument every other call site threads through at
construction time rather than per call; this class is that composition,
with zero locate logic of its own.

`kind = "SshLocate"`, mirroring `SshPosixChecksumComputer.kind =
"SshPosixChecksum"` and `SshDataExchangeScanReader.kind =
"SshDataExchange"`: every SSH-transport adapter in this family carries
an `Ssh`-prefixed kind distinct from a local counterpart, even though
`locate` has no local counterpart to distinguish itself from -- the
durable copy is by definition never on CORA's own host.
"""

from __future__ import annotations

from typing import Any

from cora.data.adapters._ssh_probe import SshProbeConfig, run_locate_probe


class SshLocateProbe:
    """`LocateProbe` that searches for the durable copy on a remote host."""

    kind = "SshLocate"

    def __init__(self, *, config: SshProbeConfig) -> None:
        self._config = config

    async def locate(
        self,
        *,
        root: str,
        months: tuple[str, ...],
        directory_suffix: str,
        filename: str,
        subdirectory: str | None,
    ) -> dict[str, Any]:
        return await run_locate_probe(
            root=root,
            months=months,
            directory_suffix=directory_suffix,
            filename=filename,
            subdirectory=subdirectory,
            config=self._config,
        )


__all__ = ["SshLocateProbe"]
