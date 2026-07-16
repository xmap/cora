"""Fail-closed write guards for a ControlPort a deployment declares unwritable.

Two guards, one per surface, because #568 gave the `ControlPortRegistry`
two: `ReadOnlyControlPort` wraps a `str`-surfaced `ControlPort` (the
`InMemoryControlPort`, and the empty-routes bare port), and
`ReadOnlySubstratePort` wraps a typed `SubstrateControlPort[AddressT]`
(the real EPICS / Tango adapters, which #568 handed a parsed
`ControlAddress` rather than a raw string). Both refuse every write and
forward `read` / `subscribe` / `aclose` to the adapter underneath.
`build_control_port` is their only construction site: it wraps each
per-route adapter BEFORE handing it to the registry, so the guard sits
between the registry and the substrate.

The two differ only in the address type their surface takes; every
argument on the docstrings below applies verbatim to both.

## Why refuse rather than consult a flag

The guard carries no routing table and asks no question at write time.
It refuses unconditionally, because the decision was already made when
`build_control_port` chose to construct it. A wrapped adapter cannot
be talked into a write; an unwrapped one was never guarded. There is
no third state, and so no arm to get wrong.

That is the whole point. The sibling route fact `is_simulated` is a
runtime QUERY with a three-valued answer: the Conductor's
`_ActuationObserver` reaches it across the `ControlPort` Protocol via
`getattr(inner, "route_is_simulated", None)`, and absent silently
means "gate inactive". That fails OPEN, which `is_simulated` survives
only because a downstream guard refuses to promote a Dataset of
unknown provenance. A write gate has no such compensator, so it must
not be built that way.

## Why below the registry, not around it

Wrapping the whole registry would satisfy the same Protocol and be
simpler, and it would be wrong twice over:

  - it would hide `route_is_simulated` from `_ActuationObserver`'s
    `getattr`, silently disabling the Dataset provenance gate;
  - it would hide `aclose` from the lifespan's teardown call.

Wrapping per-adapter leaves the registry's own surface intact and
still intercepts every modeled write, because the registry hands the
naked adapter to nobody: `route()` is called only from the registry's
own `read` / `write` / `subscribe`.

## The aclose delegation is load-bearing

`ControlPortRegistry.aclose` fans out with
`getattr(port, "aclose", None)` and SKIPS any adapter that lacks the
method. A guard without `aclose` would therefore strand every EPICS
connection it wraps: a fail-open in the LIFECYCLE rather than in the
gate. `aclose` below is not boilerplate; deleting it leaks sockets.

## Scope

`scope` records WHICH declaration refused, so an operator reading a
traceback knows whether to change an env var or a route entry:

  - `"deployment"`: `CONTROL_WRITES_ENABLED=false`, the observe-only
    safety switch, applied to every route with no exemption.
  - `"route"`: this one route carries `ControlPortRoute.read_only`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from cora.operation.ports.control_port import ControlWritesDisabledError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from cora.operation.ports.control_address import ControlAddress
    from cora.operation.ports.control_port import (
        ControlPort,
        Measurement,
        SubstrateControlPort,
    )


class ReadOnlyControlPort:
    """A `ControlPort` that observes its inner adapter but never drives it.

    Implements `ControlPort` structurally by delegating `read` and
    `subscribe`; `write` always raises `ControlWritesDisabledError`.
    """

    def __init__(
        self,
        inner: ControlPort,
        *,
        scope: Literal["deployment", "route"],
        prefix: str | None = None,
    ) -> None:
        self._inner = inner
        self._scope: Literal["deployment", "route"] = scope
        self._prefix = prefix

    async def read(self, address: str) -> Measurement:
        return await self._inner.read(address)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        """Refuse the write. No substrate is contacted.

        Signature mirrors `ControlPort.write` so the guard substitutes
        for the adapter it wraps; every argument but `address` is
        deliberately unused, because nothing downstream of here runs.
        """
        raise ControlWritesDisabledError(address, scope=self._scope, prefix=self._prefix)

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return self._inner.subscribe(address)

    async def aclose(self) -> None:
        """Close the wrapped adapter. See the module docstring: load-bearing."""
        close = getattr(self._inner, "aclose", None)
        if close is None:
            return
        await close()


class ReadOnlySubstratePort:
    """A `SubstrateControlPort` that observes its inner adapter but never drives it.

    The typed sibling of `ReadOnlyControlPort`. Implements
    `SubstrateControlPort[Any]` structurally by delegating `read` and
    `subscribe`; `write` always raises `ControlWritesDisabledError`. It
    takes a `ControlAddress` because #568's registry parses the raw
    string once and hands the substrate adapter the typed variant; the
    refusal still happens before that variant reaches any substrate.

    `str(address)` on the refusal carries the operator-facing message.
    Every `ControlAddress` variant round-trips to its original string
    via `str(...)` (see `control_address`), so the message names the
    address the operator wrote, not a dataclass repr.
    """

    def __init__(
        self,
        inner: SubstrateControlPort[Any],
        *,
        scope: Literal["deployment", "route"],
        prefix: str | None = None,
    ) -> None:
        self._inner = inner
        self._scope: Literal["deployment", "route"] = scope
        self._prefix = prefix

    async def read(self, address: ControlAddress) -> Measurement:
        return await self._inner.read(address)

    async def write(
        self,
        address: ControlAddress,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        """Refuse the write. No substrate is contacted.

        Signature mirrors `SubstrateControlPort.write` so the guard
        substitutes for the adapter it wraps; every argument but
        `address` is deliberately unused, because nothing downstream of
        here runs.
        """
        raise ControlWritesDisabledError(str(address), scope=self._scope, prefix=self._prefix)

    def subscribe(self, address: ControlAddress) -> AsyncIterator[Measurement]:
        return self._inner.subscribe(address)

    async def aclose(self) -> None:
        """Close the wrapped adapter. See the module docstring: load-bearing."""
        close = getattr(self._inner, "aclose", None)
        if close is None:
            return
        await close()


__all__ = ["ReadOnlyControlPort", "ReadOnlySubstratePort"]
