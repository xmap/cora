"""In-memory `ControlPort` adapter for unit tests and `app_env=test`.

Mirrors `cora.infrastructure.adapters.in_memory_event_store` and
`cora.infrastructure.adapters.in_memory_profile_store`: dict-backed,
no sockets, no real IOC / Tango DS / OPC UA server. Tests inject
values via `set_reading` / `simulate_disconnect` / `simulate_connect`;
production code paths call `read` / `write` / `subscribe` against
the same instance and observe the injected state.

Per [[project_test_infra]]'s 5-tier pyramid, this adapter serves the
unit tier. Production substrate adapters (Caproto / EpicsCa /
EpicsPva, plus future Tango / OPC UA) implement the same
`ControlPort` Protocol but speak real wire protocols.

## Connection model

An address is "connected" iff `set_reading` or `simulate_connect`
has been called for it. `read` and `write` against a disconnected
address raise `ControlNotConnectedError`. `simulate_disconnect`
marks a connected address as disconnected, drops its cached value
(matches real CA/PVA/OPC UA reconnect semantics), and pushes a
sentinel to every active subscriber so the subscribe iterator
raises `ControlNotConnectedError` mid-stream.

## write semantics

`write` accepts the same primitive value set as the production
adapters (`int | float | bool | str | tuple[Any, ...]`) and
constructs a `Measurement` for the store: tuples become
`kind="Array"`, other primitives become `kind="Scalar"`.
`produced_at` is read from the injectable `now` callable (defaults
to `lambda: datetime.now(tz=UTC)`); `quality` stays `"Good"`,
`quality_detail` stays `""`. Tests that need a specific kind
(`Image` / `Categorical` / `Tabular`), non-`Good` quality, or a
populated `quality_detail` use `set_reading` to push an explicit
`Measurement`.

`wait` and `timeout_s` are accepted to satisfy the Protocol but
ignored: in-memory has no substrate round-trip, so write-confirm /
timeout semantics do not apply. The contract is preserved at the
type level, mirroring how `InMemoryProfileStore.scrub_and_delete`
accepts and ignores the asyncpg `conn` parameter.

## Subscribe semantics

`subscribe` is a plain `def` that synchronously registers a
subscriber queue and returns an async iterator. The queue is
registered eagerly so a `set_reading` that lands between
`subscribe()` and the first `__anext__` still fans out (Subscriber
pattern in real CA / PVA brokers behaves the same: the listener is
hot before the first event arrives). The connect-state check fires
on the iterator's first `__anext__`, so a `subscribe()` against an
unconnected address raises `ControlNotConnectedError` through
`anext`, not at `subscribe()` time. Each subscriber gets its own
queue; pushing to an address fans out to every subscriber's queue
(no coalescing in this adapter; production adapters layer their
substrate-specific policy on top). The iterator cleans up its queue
on `aclose()` or on `ControlNotConnectedError` propagation.

## aclose

`aclose()` is a no-op for the in-memory adapter: there is no
substrate context to release. Provided so production code paths can
call `aclose()` polymorphically against any `ControlPort`
implementation without branching on type.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cora.infrastructure.logging import get_logger
from cora.operation._control_dispatch_context import get_dispatch_correlation_id
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    Measurement,
    MeasurementKind,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


_log = get_logger(__name__)
_DISPATCH_EVENT = "controlport.dispatch"
_DISPATCH_COMPLETED_EVENT = "controlport.dispatch.completed"
_DISPATCH_FAILED_EVENT = "controlport.dispatch.failed"


class _DisconnectSentinel:
    """Marker pushed to subscriber queues on `simulate_disconnect`.

    Kept as a private class (not a singleton instance) so
    `isinstance` checks in the drain loop stay unambiguous and the
    sentinel cannot collide with any legitimate `Measurement` a consumer
    might push through a future extension.
    """


_DISCONNECT = _DisconnectSentinel()
"""Module-level singleton of the disconnect marker."""


class InMemoryControlPort:
    """Process-local dict adapter for `ControlPort`.

    See module docstring for the connection model, write semantics,
    and subscribe semantics. Per-address state is kept in three
    dicts so address collisions across kinds raise type errors
    loudly rather than silently overlap.
    """

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._values: dict[str, Measurement] = {}
        self._connected: set[str] = set()
        self._subscribers: dict[str, list[asyncio.Queue[Measurement | _DisconnectSentinel]]] = {}
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(tz=UTC))
        self._closed = False

    def set_reading(self, address: str, reading: Measurement) -> None:
        """Install `reading` as the current value of `address` and fan out.

        Marks the address as connected if it was not already. Test
        entry point for seeding state before exercising production
        code paths.
        """
        self._values[address] = reading
        self._connected.add(address)
        for queue in self._subscribers.get(address, []):
            queue.put_nowait(reading)

    def simulate_connect(self, address: str) -> None:
        """Mark `address` as connected without installing a value.

        Useful for tests that want `write` to succeed (and the
        resulting `Measurement` to be observable via `read`) without
        pre-seeding a `set_reading` call.
        """
        self._connected.add(address)

    def simulate_disconnect(self, address: str) -> None:
        """Mark `address` disconnected, drop its cached value, signal subscribers.

        Subsequent `read` / `write` raise `ControlNotConnectedError`.
        Each active subscriber's iterator raises
        `ControlNotConnectedError` through the `async for` (matching
        production CA / PVA / Tango / OPC UA disconnect semantics
        where the cached value is invalidated on disconnect and must
        be re-fetched after reconnect).
        """
        self._connected.discard(address)
        self._values.pop(address, None)
        for queue in self._subscribers.get(address, []):
            queue.put_nowait(_DISCONNECT)

    async def read(self, address: str) -> Measurement:
        if address not in self._connected:
            raise ControlNotConnectedError(address)
        cached = self._values.get(address)
        if cached is None:
            raise ControlNotConnectedError(address)
        return cached

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        _ = (wait, timeout_s)
        correlation_id = get_dispatch_correlation_id()
        _log.info(
            _DISPATCH_EVENT,
            address=address,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="started",
        )
        if address not in self._connected:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlNotConnectedError.__name__,
            )
            raise ControlNotConnectedError(address)
        kind: MeasurementKind = "Array" if isinstance(value, tuple) else "Scalar"
        reading = Measurement(value=value, kind=kind, quality="Good", produced_at=self._now())
        self._values[address] = reading
        for queue in self._subscribers.get(address, []):
            queue.put_nowait(reading)
        _log.info(
            _DISPATCH_COMPLETED_EVENT,
            address=address,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="completed",
        )

    def subscribe(self, address: str) -> AsyncGenerator[Measurement]:
        """Return type narrows the Protocol's `AsyncIterator` to `AsyncGenerator`.

        Covariant return type lets tests close subscriptions via the
        iterator's `aclose()` while production callers still see the
        `AsyncIterator` contract through the Protocol surface.

        Queue registration happens synchronously here so a
        `set_reading` landing between `subscribe()` and the first
        `await anext(iterator)` still fans out. The connect-state
        check fires on the iterator's first iteration via `_drain`,
        matching the Protocol's lazy-setup contract.
        """
        queue: asyncio.Queue[Measurement | _DisconnectSentinel] = asyncio.Queue()
        self._subscribers.setdefault(address, []).append(queue)
        return self._drain(address, queue)

    async def _drain(
        self,
        address: str,
        queue: asyncio.Queue[Measurement | _DisconnectSentinel],
    ) -> AsyncGenerator[Measurement]:
        try:
            if address not in self._connected:
                raise ControlNotConnectedError(address)
            while True:
                item = await queue.get()
                if isinstance(item, _DisconnectSentinel):
                    raise ControlNotConnectedError(address)
                yield item
        finally:
            subs = self._subscribers.get(address)
            if subs is not None and queue in subs:
                subs.remove(queue)

    async def aclose(self) -> None:
        """No-op for the in-memory adapter; idempotent.

        Provided so production code paths can call `aclose()` on any
        `ControlPort` without type-checking. The dict-backed state is
        not a substrate resource; it does not need explicit release.
        """
        self._closed = True


__all__ = ["InMemoryControlPort"]
