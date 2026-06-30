"""FdtTransferPort: TransferPort over a transfer-client subprocess (FDT / scp).

The inner-leg substrate for CORA's stage-then-reconstruct: it moves a dataset's
bytes from the acquisition host to the analysis tier by running a transfer
client as a subprocess (APS Fast Data Transfer, `fdt.jar`, or scp). It is the
sibling of `GlobusTransferPort`, which serves the outer user-delivery leg; this
one serves the per-scan acquisition-to-analysis copy that gates reconstruction
(the move the 2-BM pipeline does today via `fdt.jar` or scp, tomdet:/local1 ->
/data2).

The transfer client is invoked through an injected `TransferRunner` so the
adapter is unit-testable without a real subprocess; the production runner
(`SubprocessTransferRunner`) launches and polls a real child process.

## What it does NOT do

Integrity is not established here. Per the CORA-lens design, checksum-on-arrival
is recorded as an `Attestation` (via the Data BC `ChecksumVerifier`) in the
materialize-a-Distribution edge job that consumes this port, not inside the
mover. So `verify_on_arrival` and `skip_unchanged` are not honored by this
adapter (FDT/scp offer no general sync); they are deferred to that edge job and
to richer substrates (Globus) respectively. Progress is coarse: a subprocess
exposes no per-file counters, so `observe` reports lifecycle state plus the exit
code on failure, with the counts left at their defaults.

## Not run against real FDT

Unit-tested against a fake runner; not exercised against a real `fdt.jar` or a
live host pair. Treat live behaviour as unverified until a sanity run happens.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from typing import Protocol

from cora.operation.ports.transfer_port import (
    TransferEndpointUnreachableError,
    TransferHandle,
    TransferProgress,
    TransferRejectedError,
    TransferRequest,
    TransferState,
)


class TransferRunner(Protocol):
    """Launch / poll / terminate a transfer-client subprocess.

    Injected so `FdtTransferPort` is testable with a fake. `start` returns an
    opaque token; `poll` returns the process exit code, or None while it is
    still running; `terminate` best-effort stops a running process.
    """

    async def start(self, argv: tuple[str, ...]) -> str: ...
    async def poll(self, token: str) -> int | None: ...
    async def terminate(self, token: str) -> None: ...


class SubprocessTransferRunner:
    """Production `TransferRunner` backed by asyncio child processes.

    Not unit-tested (it launches real processes); the adapter's behaviour is
    covered against a fake runner. `poll` reads the process's `returncode`,
    which the event loop sets when the child exits.
    """

    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._counter = 0

    async def start(self, argv: tuple[str, ...]) -> str:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._counter += 1
        token = f"fdt-proc-{self._counter}"
        self._processes[token] = process
        return token

    async def poll(self, token: str) -> int | None:
        return self._processes[token].returncode

    async def terminate(self, token: str) -> None:
        process = self._processes[token]
        if process.returncode is None:
            process.terminate()


@dataclass
class _MoveState:
    """Per-handle bookkeeping the adapter keeps alongside the runner's token."""

    cancelled: bool = False


@dataclass
class FdtTransferPort:
    """`TransferPort` that moves bytes by running a transfer-client subprocess.

    `fdt_jar` and `java` locate the Fast Data Transfer client. A deployment that
    moves via scp would supply a sibling adapter at the rule-of-three trigger;
    this one builds an `fdt.jar` client invocation. See the module docstring for
    what this adapter deliberately does not do.
    """

    runner: TransferRunner
    fdt_jar: str = "/APSshare/bin/fdt.jar"
    java: str = "java"
    _moves: dict[TransferHandle, _MoveState] = field(
        default_factory=dict[TransferHandle, _MoveState]
    )

    async def begin(self, request: TransferRequest) -> TransferHandle:
        _, source_path = _split_location(request.source)
        dest_host, dest_dir = _split_location(request.destination)
        argv: tuple[str, ...] = (self.java, "-jar", self.fdt_jar, "-c", dest_host, "-d", dest_dir)
        if request.recursive:
            argv += ("-r",)
        argv += (source_path,)
        try:
            token = await self.runner.start(argv)
        except OSError as exc:
            raise TransferEndpointUnreachableError(request.destination) from exc
        handle = TransferHandle(token)
        self._moves[handle] = _MoveState()
        return handle

    async def observe(self, handle: TransferHandle) -> TransferProgress:
        move = self._moves[handle]
        if move.cancelled:
            return TransferProgress(state=TransferState.CANCELLED)
        returncode = await self.runner.poll(str(handle))
        if returncode is None:
            return TransferProgress(state=TransferState.ACTIVE)
        if returncode == 0:
            return TransferProgress(state=TransferState.SUCCEEDED)
        return TransferProgress(
            state=TransferState.FAILED,
            detail=f"transfer client exited with code {returncode}",
        )

    async def cancel(self, handle: TransferHandle) -> None:
        move = self._moves[handle]
        returncode = await self.runner.poll(str(handle))
        if returncode is not None:
            return
        await self.runner.terminate(str(handle))
        move.cancelled = True

    async def aclose(self) -> None:
        for handle in list(self._moves):
            with contextlib.suppress(Exception):
                await self.runner.terminate(str(handle))


def _split_location(location: str) -> tuple[str, str]:
    """Split a CORA `host:path` location into (host, path).

    Raises `TransferRejectedError` on a malformed location before any subprocess
    launch, so an authoring error fails fast rather than spawning a broken move.
    """
    host, separator, path = location.partition(":")
    if not separator or not host or not path:
        msg = f"location {location!r} is not in 'host:path' form"
        raise TransferRejectedError(msg)
    return host, path


__all__ = ["FdtTransferPort", "SubprocessTransferRunner", "TransferRunner"]
