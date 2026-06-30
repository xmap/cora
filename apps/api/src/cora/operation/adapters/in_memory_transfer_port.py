"""In-memory `TransferPort` test double for unit / scenario tiers.

Dict-backed, no substrate. A test seeds the observation progression a begun
move will report; the engine-under-test calls `begin` / `observe` / `cancel`
against the same instance and walks the seeded snapshots toward a terminal.
This is the only `TransferPort` adapter that exists: there is no production
substrate adapter yet, because the build trigger has not fired (see
`cora.operation.ports.transfer_port`). The fake serves the triage that asks
whether a transfer is a conductor step or a long-running edge job.

## Seeding model

A move reports a SEQUENCE of `TransferProgress` snapshots, one per `observe`,
clamping on the last. That models the real shape the synchronous compute fake
cannot: a move that is `Active` for several polls before a terminal, or that
goes `Suspended` mid-flight and waits. `set_next_progression` seeds the whole
sequence the next begun move yields (FIFO across begins); `set_next_terminal`
is the one-snapshot convenience for a move that is observed at its terminal
straight away. With nothing seeded a move succeeds on first observe, so a
happy-path test needs no seeding. `set_next_begin_error` seeds a substrate
refusal the next `begin` raises.

## Cancellation

`cancel` flips a non-terminal move so subsequent `observe` reports `Cancelled`,
carrying the last seen counts; cancelling an already-terminal move is a no-op,
matching the port contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cora.operation.ports.transfer_port import (
    TransferHandle,
    TransferProgress,
    TransferRequest,
    TransferState,
)


@dataclass
class _Movement:
    """The seeded observation sequence bound to one begun handle."""

    request: TransferRequest
    snapshots: list[TransferProgress]
    cursor: int = 0
    cancelled: bool = False
    last_returned: TransferProgress | None = None


@dataclass
class InMemoryTransferPort:
    """Process-local dict adapter for `TransferPort`.

    See module docstring for the seeding model and cancellation behaviour.
    """

    _progressions: list[tuple[TransferProgress, ...]] = field(
        default_factory=list[tuple[TransferProgress, ...]]
    )
    _begin_errors: list[Exception] = field(default_factory=list[Exception])
    _movements: dict[TransferHandle, _Movement] = field(
        default_factory=dict[TransferHandle, _Movement]
    )
    _counter: int = 0
    _closed: bool = False

    def set_next_progression(self, snapshots: tuple[TransferProgress, ...]) -> None:
        """Seed the observation sequence the next begun move yields (FIFO).

        Each `observe` returns the next snapshot, clamping on the last, so a
        sequence like `(Active, Active, Succeeded)` models a move polled to a
        terminal. An empty sequence is rejected (a move always reports
        something).
        """
        if not snapshots:
            msg = "a transfer progression needs at least one snapshot"
            raise ValueError(msg)
        self._progressions.append(snapshots)

    def set_next_terminal(
        self,
        state: TransferState,
        *,
        bytes_moved: int = 0,
        files_total: int | None = None,
        files_moved: int = 0,
        files_skipped: int = 0,
        files_failed: int = 0,
        detail: str | None = None,
    ) -> None:
        """Seed a single-snapshot progression observed at `state` straight away.

        Convenience over `set_next_progression` for a move a test wants to read
        at its terminal (or any single state) without a multi-step sequence.
        """
        self.set_next_progression(
            (
                TransferProgress(
                    state=state,
                    bytes_moved=bytes_moved,
                    files_total=files_total,
                    files_moved=files_moved,
                    files_skipped=files_skipped,
                    files_failed=files_failed,
                    detail=detail,
                ),
            )
        )

    def set_next_begin_error(self, error: Exception) -> None:
        """Seed an exception the next `begin` raises (FIFO), e.g. a refusal."""
        self._begin_errors.append(error)

    async def begin(self, request: TransferRequest) -> TransferHandle:
        if self._begin_errors:
            raise self._begin_errors.pop(0)
        self._counter += 1
        handle = TransferHandle(f"inmem-transfer-{self._counter}")
        if self._progressions:
            snapshots = list(self._progressions.pop(0))
        else:
            snapshots = [TransferProgress(state=TransferState.SUCCEEDED)]
        self._movements[handle] = _Movement(request=request, snapshots=snapshots)
        return handle

    async def observe(self, handle: TransferHandle) -> TransferProgress:
        movement = self._movements[handle]
        if movement.cancelled:
            base = movement.last_returned or movement.snapshots[0]
            snapshot = TransferProgress(
                state=TransferState.CANCELLED,
                bytes_moved=base.bytes_moved,
                files_total=base.files_total,
                files_moved=base.files_moved,
                files_skipped=base.files_skipped,
                files_failed=base.files_failed,
            )
            movement.last_returned = snapshot
            return snapshot
        snapshot = movement.snapshots[movement.cursor]
        if movement.cursor < len(movement.snapshots) - 1:
            movement.cursor += 1
        movement.last_returned = snapshot
        return snapshot

    async def cancel(self, handle: TransferHandle) -> None:
        movement = self._movements[handle]
        if movement.last_returned is not None and movement.last_returned.state.is_terminal:
            return
        movement.cancelled = True

    async def aclose(self) -> None:
        """No-op for the in-memory double; idempotent."""
        self._closed = True


__all__ = ["InMemoryTransferPort"]
