"""Prefix-routed `ControlPort` composite for multi-substrate deployments.

Per [[project_control_port_design]] and
[[project_control_port_generalization_research]], production
deployments run more than one substrate adapter side by side: 2-BM's
CA-only IOCs alongside detector PVs served via PVA, plus Tango device
servers (ESRF BLISS, MAX IV) and eventually OPC UA endpoints. The
executor needs ONE `ControlPort` to talk to; the registry is that one.

## Two surfaces meet here

The registry is the seam between the caller-facing `ControlPort` (`str`
addresses, because the Conductor cannot know a substrate from a recipe
step) and the substrate adapters' `SubstrateControlPort` (typed
`ControlAddress`). For each call it matches a route by string prefix,
parses the string into the `ControlAddress` variant the matched route's
substrate dictates (`parse_control_address`), and dispatches to the
matched `SubstrateControlPort`. A malformed address surfaces as
`MalformedControlAddressError` at this boundary, a routing miss as
`NoAdapterForAddressError`.

## Routing rule

Longest-prefix-match by address string. Routes are registered in
arbitrary order; lookup sorts by prefix length descending so a more
specific route (`"2bma:cam:image"`) wins over a more general one
(`"2bma:"`). This matches the longest-match precedent every other
config-driven address router (HAProxy, nginx `location`, Tango's
`TANGO_HOST` table) uses, and avoids the "first match wins" foot-gun
where registration order silently changes behaviour.

No regex, no glob: a prefix is a plain string. Substrates address
namespaces via stable prefix conventions (EPICS sites use facility-
prefix like `2bma:`; Tango uses `domain/family/member`; OPC UA uses
`ns=N;`). When a real deployment needs a smarter router, this class
is the seam to widen, not the executor.

## In-memory routes

`InMemoryControlPort` is `str`-surfaced (it is also the caller-facing
double used by 148 test sites), so it is not a `SubstrateControlPort`.
The registry wraps it in `_StrAddressSubstratePort`, a thin shim that
unwraps a `ControlAddress` back to its string and delegates. That keeps
the in-memory adapter untouched while letting the registry's typed
dispatch treat every route uniformly.

## Lifecycle

`aclose()` calls `aclose()` on every registered adapter in
registration order, suppressing exceptions so a flaky adapter
can't strand its siblings. Idempotent: second call is a no-op.

## Out of scope at v1

- Per-substrate fallback on connect-error (not needed; the address
  prefix uniquely identifies the substrate).
- Connection-pool sharing across same-substrate routes (each adapter
  owns its own state; sharing would require coordinated lifecycle).
- Health-probe demotion of degraded adapters (deferred to executor
  layer; the registry is a router, not a load balancer).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from cora.operation.ports.control_address import parse_control_address
from cora.operation.ports.control_port import (
    Measurement,
    NoAdapterForAddressError,
    SubstrateControlPort,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from cora.infrastructure.control_port_route import Substrate
    from cora.operation.ports.control_address import ControlAddress
    from cora.operation.ports.control_port import ControlPort


class _StrAddressSubstratePort:
    """Adapt a `str`-surfaced `ControlPort` to the typed `SubstrateControlPort`.

    Wraps `InMemoryControlPort` (and any other `str`-address port) so the
    registry's typed dispatch can hold it in the same route table as the
    real substrate adapters. Unwraps each `ControlAddress` to its string
    via `str(...)` and delegates verbatim.
    """

    def __init__(self, inner: ControlPort) -> None:
        self._inner = inner

    async def read(self, address: ControlAddress) -> Measurement:
        return await self._inner.read(str(address))

    async def write(
        self,
        address: ControlAddress,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        await self._inner.write(str(address), value, wait=wait, timeout_s=timeout_s)

    def subscribe(self, address: ControlAddress) -> AsyncIterator[Measurement]:
        return self._inner.subscribe(str(address))

    async def aclose(self) -> None:
        close = getattr(self._inner, "aclose", None)
        if close is not None:
            await close()


class ControlPortRegistry:
    """Prefix-routed composite implementing `ControlPort`.

    Construct empty, call `register_substrate_port(prefix, port, substrate)` for each
    substrate route at app startup, then hand the registry to the
    executor as a single `ControlPort`. The executor never sees the
    routing table.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, SubstrateControlPort[Any], Substrate, bool]] = []
        self._closed = False

    def register_substrate_port(
        self,
        prefix: str,
        port: SubstrateControlPort[Any],
        substrate: Substrate,
        *,
        is_simulated: bool = False,
    ) -> None:
        """Add a route. Calling with a prefix already registered replaces it.

        `substrate` names the address family the registry parses `str`
        addresses into for this route (`parse_control_address`).
        Replacement is intentional: hot-swapping a substrate adapter
        during integration tests should not require dropping and
        reconstructing the registry.

        `is_simulated` marks the route as driving a simulator (declared
        per deployment, not inferred from the adapter class); it feeds
        `route_is_simulated` and, downstream, the Dataset provenance gate.
        """
        self._routes = [(p, a, s, sim) for (p, a, s, sim) in self._routes if p != prefix]
        self._routes.append((prefix, port, substrate, is_simulated))

    def register_control_port(
        self,
        prefix: str,
        port: ControlPort,
        substrate: Substrate = "in_memory",
        *,
        is_simulated: bool = False,
    ) -> None:
        """Register a `str`-surfaced `ControlPort` (e.g. `InMemoryControlPort`).

        Wraps `port` in the module-private `_StrAddressSubstratePort` shim so the
        typed route table can hold it uniformly with the real substrate
        adapters, keeping the shim an implementation detail callers never name.
        `substrate` defaults to `in_memory` because that is the only
        `str`-surfaced adapter today; pass another value only if a future
        `str`-address adapter routes under a different parsing family.
        """
        self.register_substrate_port(
            prefix, _StrAddressSubstratePort(port), substrate, is_simulated=is_simulated
        )

    def route(self, address: str) -> SubstrateControlPort[Any]:
        """Return the adapter for `address` via longest-prefix-match.

        Raises `NoAdapterForAddressError` when no registered prefix
        is a prefix of `address`. The error carries the address so
        operators can spot the missing route from logs alone.
        """
        port, _substrate = self._resolve(address)
        return port

    def _resolve(self, address: str) -> tuple[SubstrateControlPort[Any], Substrate]:
        """Longest-prefix-match returning the adapter and its substrate."""
        for prefix, port, substrate, _sim in sorted(self._routes, key=lambda r: -len(r[0])):
            if address.startswith(prefix):
                return port, substrate
        raise NoAdapterForAddressError(address)

    def route_is_simulated(self, address: str) -> bool:
        """Return whether `address`'s route drives a simulator.

        Same longest-prefix-match as `route`, returning the route's
        declared `is_simulated` flag. Raises `NoAdapterForAddressError`
        when no registered prefix matches, so the caller cannot mistake
        an unrouted address for a physical one.
        """
        for prefix, _port, _substrate, is_simulated in sorted(
            self._routes, key=lambda r: -len(r[0])
        ):
            if address.startswith(prefix):
                return is_simulated
        raise NoAdapterForAddressError(address)

    async def read(self, address: str) -> Measurement:
        port, substrate = self._resolve(address)
        return await port.read(parse_control_address(address, substrate))

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        port, substrate = self._resolve(address)
        await port.write(
            parse_control_address(address, substrate), value, wait=wait, timeout_s=timeout_s
        )

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        port, substrate = self._resolve(address)
        return port.subscribe(parse_control_address(address, substrate))

    async def aclose(self) -> None:
        """Close every registered adapter; idempotent.

        Suppresses per-adapter close errors so one flaky adapter
        can't strand siblings. Production deployments call this
        from the FastAPI lifespan exit handler.
        """
        if self._closed:
            return
        self._closed = True
        for _, port, _substrate, _is_simulated in self._routes:
            close = getattr(port, "aclose", None)
            if close is None:
                continue
            with contextlib.suppress(Exception):
                await close()


__all__ = ["ControlPortRegistry"]
