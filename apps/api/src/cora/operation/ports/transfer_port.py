"""TransferPort: CORA's domain-shaped seam for moving a dataset's bytes.

`TransferPort` is the async Protocol the conducting engine uses to begin a
bulk byte movement, observe its progress, and cancel it. It is owned and
shaped by CORA, from what CORA's own domain needs: the engine has to start a
move, watch a possibly long-running move toward a terminal, and learn whether
every byte arrived so the Data BC can mark the landed `Distribution` verified.
Concrete substrates (a Globus transfer task, the APS Data Management DAQ
service, an S3 copy) are OUTSIDE adapters that get tested against this shape
later; they do not define it. An adapter translates the substrate's wire
vocabulary into the CORA-owned value types below, the same ACL posture the
control and compute adapters take.

This is the data-movement member of CORA's actuation seam, alongside
`ControlPort` (drive hardware) and `ComputePort` (drive a compute job). All
three are seams the engine reaches across to actuate the outside world; per
the seam model, moving bytes through Globus is the same posture as driving a
motor through EPICS, not a competition with it. The three are siblings in
role, not copies in shape: a transfer is neither value-IO nor a single job,
so its surface is its own.

## Earned, not minted

Adapters now exist (`InMemoryTransferPort` for tests; `FdtTransferPort` and
`GlobusTransferPort` as real substrates), and `cora.api._distribution_materializer`
consumes the port. But nothing constructs any of it: there is no transfer-port
factory (no `build_transfer_port` sibling to `build_control_port`), the only
consumer takes its port as an injected field, and that consumer is itself
never constructed in `src`. `test_dormant_outbound_seams_unwired` pins the
real adapters as unconstructed. So the executing aggregate and the
composition-root wiring still wait on the build trigger: a promote or publish
rule that blocks on a transfer outcome, an in-path substrate with a native
partial terminal, or a custody chain the existing `Attestation` path cannot
carry. Until one fires, the real adapters are dormant code, not a live egress
path.

## Why `begin` / `observe` / `cancel`, not blocking submit-and-await

`ComputePort` blocks (`submit` then `await_terminal_state`) because a compute
job is bounded: a reconstruction runs for minutes and the engine can hold the
call open. A transfer is different in kind. It can be large, slow, and partial:
a sync of an experiment directory may move for hours, may stall waiting for a
credential to be renewed, and may finish with most files moved but a few
failed. So the engine does not block on a transfer; it begins one, gets back
an opaque handle, and observes that handle on its own cadence until the
progress reports a terminal state. That non-blocking begin-then-observe shape
is the whole reason a transfer wants a long-running edge job rather than a
synchronous step.

## Out of scope (deferred, each with its trigger)

- A routing registry / multi-substrate dispatch. Triggers at the second real
  adapter, exactly as ControlPort earned its registry from a third substrate.
- A `PartiallyFailed` terminal state. The first real substrate (Globus) has no
  native partial terminal: a sync that skips unchanged files still ends
  succeeded, and a genuine partial appears only as a failed terminal carrying
  a non-zero failed-file count. So partial-ness is carried on `TransferProgress`
  (a terminal `Failed` with `files_failed > 0` and `files_moved > 0`), not as
  an enum value, until an adapter with a native partial terminal earns it.
- Resume of an interrupted transfer. Does not generalize across substrates
  (a directory sync re-derives its own delta; a single-file move restarts);
  capability-flagged when a substrate needs it.

## Actuation kind

`ActuationKind` (Physical / Simulated / Hybrid) is deliberately NOT on this
surface. It is a property of the ROUTE a move is dispatched to, not of the
port, so the engine observes it from the routing table the same way the
control path does, never from the transfer adapter class. A rehearsal move on
a simulated route taints its output exactly as a simulated control episode
does.

## Integrity

`verify_on_arrival` asks the substrate to self-check that the bytes that
landed match the source and re-move on mismatch. It is a convenience that
fails a bad move early. It does NOT replace CORA's authoritative custody
record: the landed `Distribution` becomes verified only through the Data BC's
`Attestation` path (`ChecksumVerifier`), which walks the bytes CORA can see.

## Exceptions

Six exception families describe the move's failure modes. `TransferPort` is
not REST-accessible; the executing edge job captures these as event-payload
metadata per the non-determinism principle, never as HTTP errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType, Protocol, runtime_checkable

TransferHandle = NewType("TransferHandle", str)
"""Opaque substrate handle to one begun move, returned by `begin`.

The substrate mints it (a Globus task id, a DM DAQ directory key, an S3 copy
token); the engine treats it as an opaque correlation key it passes back to
`observe` and `cancel`, and snapshots onto the edge job's event for audit. A
separate CORA-supplied `idempotency_key` on the request (not this handle) is
what makes a retried `begin` safe.
"""


class TransferState(StrEnum):
    """The coarse lifecycle of one move, as CORA needs to drive its edge job.

    Adapters MAP a substrate's own statuses into these; the set is CORA's, not
    any substrate's. There is one in-flight value, one intervention value, and
    three terminals.

    `Pending`: begun and accepted, not yet observed moving.
    `Active`: bytes are moving.
    `Suspended`: stalled and will not continue without intervention (the
        canonical cause is an expired credential on a long sync). NOT a
        terminal: a renewed credential returns it to `Active`.
    `Succeeded`: the move finished and every in-scope byte arrived. A sync that
        skipped unchanged files still ends here.
    `Failed`: the move reached a terminal without full success. This carries
        BOTH the total-failure case (`files_moved == 0`) and the partial case
        (`files_moved > 0` and `files_failed > 0`); the counts on
        `TransferProgress` tell them apart. A caller-issued `cancel` also lands
        here unless the substrate distinguishes it (see `Cancelled`).
    `Cancelled`: the move stopped because the engine asked it to. Distinct from
        `Failed` so an operator reads "we stopped this" differently from "this
        broke," for substrates that report the difference.
    """

    PENDING = "Pending"
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"

    @property
    def is_terminal(self) -> bool:
        """True for the three end states; False for Pending / Active / Suspended.

        Suspended is explicitly non-terminal: it is the long-sync intervention
        state the engine waits through, not an end the edge job folds on.
        """
        return self in {TransferState.SUCCEEDED, TransferState.FAILED, TransferState.CANCELLED}


@dataclass(frozen=True)
class TransferRequest:
    """What CORA asks a substrate to move, in CORA's own vocabulary.

    `source` and `destination` are CORA location strings the routed adapter
    parses (a Globus `endpoint_id:/path`, a DM `@host:/path`, an `s3://`
    URI); at v1 they are plain strings, promoted to a typed location sum at
    the second-substrate trigger, the same path `ControlPort.address` reserves.
    `recursive` declares the source is a directory tree, not a single file.
    `skip_unchanged` asks the substrate not to re-move bytes already present and
    identical at the destination (a re-sync of an experiment directory).
    `verify_on_arrival` asks the substrate to self-check integrity and re-move
    on mismatch (see module docstring: this does not replace the Attestation
    record). `label` is an operator-facing name for the move. `idempotency_key`
    is a CORA-minted key that lets a retried `begin` dedupe at the substrate
    instead of starting a duplicate move, so a replay stays deterministic.
    """

    source: str
    destination: str
    recursive: bool = False
    skip_unchanged: bool = False
    verify_on_arrival: bool = False
    label: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class TransferProgress:
    """A snapshot of one move, returned by `observe`.

    Carries the lifecycle `state` plus the coarse counts CORA needs to fold
    onto its edge job and show an operator. `files_total` is None until the
    substrate has finished scanning (it can grow as a recursive move discovers
    directories). `files_skipped` counts unchanged files a `skip_unchanged`
    move did not re-move. `files_failed` is the partial signal: on a terminal
    `Failed` state, `files_failed > 0` with `files_moved > 0` is a partial
    move, while `files_moved == 0` is a total failure. `detail` carries the
    substrate's human-readable sub-status (a stall reason, a fatal-error
    summary) for the operator-facing record.
    """

    state: TransferState
    bytes_moved: int = 0
    files_total: int | None = None
    files_moved: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    detail: str | None = None

    @property
    def is_partial(self) -> bool:
        """True for a terminal `Failed` that nonetheless moved some files.

        The carried-on-counts stand-in for a native `PartiallyFailed` terminal
        (deferred until a substrate reports one). Lets a consumer separate
        "moved most of it, some failed" from "moved nothing."
        """
        return self.state is TransferState.FAILED and self.files_moved > 0 and self.files_failed > 0


class TransferEndpointUnreachableError(Exception):
    """The source or destination substrate could not be reached at all.

    A configuration or environment gap (endpoint offline, host unresolvable,
    credentials absent), not a rejection of the specific move. Distinct from
    `TransferRejectedError`: the substrate is unreachable, not refusing.
    """

    def __init__(self, endpoint: str) -> None:
        super().__init__(f"Transfer endpoint {endpoint!r} unreachable")
        self.endpoint = endpoint


class TransferRejectedError(Exception):
    """The substrate refused the move at begin time.

    A malformed path, a quota breach, an unsupported source/destination pair.
    The substrate is reachable; it is this move it would not accept.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Transfer rejected: {reason}")
        self.reason = reason


class TransferAccessDeniedError(Exception):
    """The substrate denied access to a location.

    Credentials present but insufficient for the source read or destination
    write. Distinct from `TransferEndpointUnreachableError` (no credentials /
    no endpoint) so an operator separates "you may not" from "it is not there."
    """

    def __init__(self, endpoint: str) -> None:
        super().__init__(f"Transfer access denied for {endpoint!r}")
        self.endpoint = endpoint


class TransferIntegrityError(Exception):
    """A verify-on-arrival check found landed bytes that do not match the source.

    Raised only when the substrate definitively reports an integrity failure it
    will not resolve by re-moving. The edge job records a failed move; no
    `Distribution` is marked verified off mismatched bytes.
    """

    def __init__(self, handle: TransferHandle, location: str) -> None:
        super().__init__(f"Transfer {handle!r} integrity check failed at {location!r}")
        self.handle = handle
        self.location = location


class TransferTimeoutError(Exception):
    """An adapter's own status call exceeded its ceiling before answering.

    The adapter giving up on a substrate that never reported back, distinct
    from a move that is legitimately slow (that is an `Active` observation the
    engine keeps watching). Carries the breached ceiling so logs separate "we
    stopped asking" from "the move ran long."
    """

    def __init__(self, handle: TransferHandle, timeout_s: float) -> None:
        super().__init__(f"Transfer {handle!r} status call exceeded {timeout_s}s")
        self.handle = handle
        self.timeout_s = timeout_s


class NoRouteForLocationError(Exception):
    """No registered adapter route matches a request location.

    Almost always a configuration gap (a new endpoint or scheme without a
    matching route). The mirror of the control path's no-adapter-for-address
    miss; lives next to the port so a routing layer can raise it.
    """

    def __init__(self, location: str) -> None:
        super().__init__(f"Transfer location {location!r} has no matching adapter")
        self.location = location


@runtime_checkable
class TransferPort(Protocol):
    """CORA-owned seam for moving a dataset's bytes across a substrate.

    Substrate-agnostic. Concrete adapters (a future `GlobusTransferPort`,
    `DmDaqTransferPort`, `S3TransferPort`) implement the wire details and map
    their statuses into `TransferState`; the engine never touches a
    substrate-specific symbol. Non-blocking by design: `begin` returns a handle
    and the engine `observe`s it to a terminal on its own cadence, because a
    transfer can be long-running, can suspend mid-flight, and can finish
    partially. A routing registry, a native partial terminal, and resume are
    deferred to their own triggers (see module docstring).
    """

    async def begin(self, request: TransferRequest) -> TransferHandle:
        """Begin the move described by `request` and return its handle.

        Returns as soon as the substrate accepts the move (a submitted task, a
        started sync). Raises `TransferRejectedError` if the substrate refuses
        the request, `TransferEndpointUnreachableError` if a substrate is
        unreachable, `TransferAccessDeniedError` on a permission denial, or
        `NoRouteForLocationError` if no adapter route matches a location.
        """
        ...

    async def observe(self, handle: TransferHandle) -> TransferProgress:
        """Return a current `TransferProgress` snapshot for `handle`.

        Non-blocking: reports wherever the move is now (`Pending` / `Active` /
        `Suspended` or a terminal), so the engine polls on its own cadence
        rather than holding a call open. Raises
        `TransferEndpointUnreachableError` or `TransferAccessDeniedError` if the
        status cannot be read, `TransferTimeoutError` if the adapter's status
        call itself times out, or `TransferIntegrityError` when the substrate
        definitively reports a verify-on-arrival mismatch.
        """
        ...

    async def cancel(self, handle: TransferHandle) -> None:
        """Ask the substrate to stop the move identified by `handle`.

        Best-effort and idempotent: cancelling an already-terminal move is a
        no-op. A successfully cancelled move is observed as `Cancelled` (or
        `Failed` on a substrate that does not distinguish the two).
        """
        ...

    async def aclose(self) -> None:
        """Release any substrate resources; idempotent.

        Provided so composition code can `aclose()` any `TransferPort` without
        branching on type, the same affordance the control and compute ports
        offer. A dict-backed test double is a no-op.
        """
        ...


__all__ = [
    "NoRouteForLocationError",
    "TransferAccessDeniedError",
    "TransferEndpointUnreachableError",
    "TransferHandle",
    "TransferIntegrityError",
    "TransferPort",
    "TransferProgress",
    "TransferRejectedError",
    "TransferRequest",
    "TransferState",
    "TransferTimeoutError",
]
