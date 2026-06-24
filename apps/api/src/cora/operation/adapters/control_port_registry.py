"""Prefix-routed `ControlPort` composite for multi-substrate deployments.

Per [[project_control_port_design]] § Address space and
[[project_control_port_generalization_research]], production
deployments will run more than one substrate adapter side by side:
2-BM's CA-only IOCs alongside detector PVs served via PVA, plus
eventually Tango device servers and OPC UA endpoints in other
facilities. The executor needs ONE `ControlPort` to talk to; the
registry is that one.

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

from cora.operation.ports.control_port import (
    ControlPort,
    Measurement,
    NoAdapterForAddressError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ControlPortRegistry:
    """Prefix-routed composite implementing `ControlPort`.

    Construct empty, call `register(prefix, port)` for each substrate
    route at app startup, then hand the registry to the executor as a
    single `ControlPort`. The executor never sees the routing table.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, ControlPort, bool]] = []
        self._closed = False

    def register(self, prefix: str, port: ControlPort, *, is_simulated: bool = False) -> None:
        """Add a route. Calling with a prefix already registered replaces it.

        Replacement is intentional: hot-swapping a substrate adapter
        during integration tests should not require dropping and
        reconstructing the registry.

        `is_simulated` marks the route as driving a simulator (declared
        per deployment, not inferred from the adapter class); it feeds
        `route_is_simulated` and, downstream, the Dataset provenance gate.
        """
        self._routes = [(p, a, s) for (p, a, s) in self._routes if p != prefix]
        self._routes.append((prefix, port, is_simulated))

    def route(self, address: str) -> ControlPort:
        """Return the adapter for `address` via longest-prefix-match.

        Raises `NoAdapterForAddressError` when no registered prefix
        is a prefix of `address`. The error carries the address so
        operators can spot the missing route from logs alone.
        """
        for prefix, port, _is_simulated in sorted(self._routes, key=lambda r: -len(r[0])):
            if address.startswith(prefix):
                return port
        raise NoAdapterForAddressError(address)

    def route_is_simulated(self, address: str) -> bool:
        """Return whether `address`'s route drives a simulator.

        Same longest-prefix-match as `route`, returning the route's
        declared `is_simulated` flag. Raises `NoAdapterForAddressError`
        when no registered prefix matches, so the caller cannot mistake
        an unrouted address for a physical one.
        """
        for prefix, _port, is_simulated in sorted(self._routes, key=lambda r: -len(r[0])):
            if address.startswith(prefix):
                return is_simulated
        raise NoAdapterForAddressError(address)

    async def read(self, address: str) -> Measurement:
        return await self.route(address).read(address)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        await self.route(address).write(address, value, wait=wait, timeout_s=timeout_s)

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return self.route(address).subscribe(address)

    async def aclose(self) -> None:
        """Close every registered adapter; idempotent.

        Suppresses per-adapter close errors so one flaky adapter
        can't strand siblings. Production deployments call this
        from the FastAPI lifespan exit handler.
        """
        if self._closed:
            return
        self._closed = True
        for _, port, _is_simulated in self._routes:
            close = getattr(port, "aclose", None)
            if close is None:
                continue
            with contextlib.suppress(Exception):
                await close()


__all__ = ["ControlPortRegistry"]
