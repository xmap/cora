"""Operation BC factory: materialise a `ControlPort` from deployment routes.

`build_control_port(routes, writes_enabled=...)` consumes the typed
`list[ControlPortRoute]` carried on `Settings.control_port_routes`
and returns either:

  - `InMemoryControlPort` (empty list / no env var set; legacy default
    + test convenience; preserves the v1 wire-up behavior for tests +
    deployments that have not yet opted in to a substrate)
  - `ControlPortRegistry` populated with the configured substrate
    adapters per prefix (longest-prefix match dispatch, per
    `cora.operation.adapters.control_port_registry`)

Either shape is subject to the write guard: when `writes_enabled` is
False (the default deployment posture), every adapter this factory
constructs is wrapped in a `ReadOnlyControlPort` before it is handed
out, so the returned port observes but never drives. See the
`## Write posture` section below.

The typed route shape + `Substrate` literal live in
`cora.infrastructure.control_port_route` so `Settings` can validate
the env var without importing BC-specific adapter classes.

## Substrate choices

  - `in_memory`: process-local dict (`InMemoryControlPort`). Tests +
    deployments that want a no-op port (the slice surface is
    reachable but no real substrate is exercised).
  - `epics_ca`: production CA via aioca (`EpicsCaControlPort`).
  - `epics_pva`: production PVA via p4p (`EpicsPvaControlPort`).
  - `tango`: Tango device attributes via PyTango (`TangoControlPort`).
    Ships under the optional `tango` dependency group; selecting it
    without the extra installed raises `ValueError` at construction
    (probed via `_optional_tango.require_tango`).

Future substrates (`opc_ua`) land as additive code edits in
`cora.infrastructure.control_port_route` (literal) plus a new arm in
`_build_substrate` here.

## Write posture

`writes_enabled` (from `Settings.control_writes_enabled`, default
False) decides whether this factory hands out a port that can drive
anything. False wraps every adapter in a `ReadOnlyControlPort`, with
no per-substrate exemption; the per-route `read_only` flag carves a
read-only hole in an otherwise writable deployment. The guard is
applied here, at construction, rather than consulted at write time:
that is what makes it fail closed.

Scope: this covers the ControlPort only. `ComputePort` with
`COMPUTE_SUBSTRATE=local_process` spawns caller-supplied argv and can
reach a control system without passing through this factory at all.

## Lifecycle

The returned port owns the lifecycle of every adapter it constructs:
`aclose()` on the returned port fans out to each adapter (registry
path) or is a no-op (in-memory path). The caller (`wire_operation`)
does NOT track individual adapters.
"""

from collections.abc import Sequence
from typing import Any, Literal

from cora.infrastructure.control_port_route import ControlPortRoute, Substrate
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.read_only_control_port import (
    ReadOnlyControlPort,
    ReadOnlySubstratePort,
)
from cora.operation.adapters.tango_control_port import TangoControlPort
from cora.operation.ports.control_port import ControlPort, SubstrateControlPort


def build_control_port(routes: Sequence[ControlPortRoute], *, writes_enabled: bool) -> ControlPort:
    """Materialise the ControlPort the Conductor talks to.

    Empty routes returns a single `InMemoryControlPort` (legacy
    default + test convenience). Non-empty routes returns a
    `ControlPortRegistry` populated with the configured substrate
    adapters per prefix. `in_memory` routes go through
    `register_control_port` (the registry wraps the `str`-surfaced
    adapter); the real substrate adapters register directly on the
    typed surface.

    `writes_enabled` is required and has NO default: every caller
    states the deployment's write posture on purpose. False wraps
    EVERY adapter in a read-only guard, including the empty-routes
    in-memory one and including routes that never declared `read_only`.
    There is deliberately no per-substrate exemption: an exemption is a
    partial application, and not-partially-applicable is the single
    property the switch exists to have. A soft IOC speaks real Channel
    Access, so inferring safety from the substrate is exactly the
    mistake `ControlPortRoute.is_simulated` exists to prevent.

    The guard comes in two surfaces because #568's registry does: the
    `str`-surfaced `InMemoryControlPort` is wrapped by
    `ReadOnlyControlPort` before `register_control_port` shims it, and a
    typed substrate adapter is wrapped by `ReadOnlySubstratePort` before
    `register_substrate_port` holds it. Both refuse `write` and delegate
    `read` / `subscribe` / `aclose`.

    Raises `ValueError` on a duplicate prefix. `register_substrate_port`
    is last-wins by design, which was harmless when routes carried only
    dispatch and provenance, but silently dropping a route now silently
    drops a `read_only` safety declaration.
    """
    _reject_duplicate_prefixes(routes)
    if not routes:
        return _guarded_str(InMemoryControlPort(), read_only=not writes_enabled, scope="deployment")
    registry = ControlPortRegistry()
    for route in routes:
        read_only = not writes_enabled or route.read_only
        scope: Literal["deployment", "route"] = "deployment" if not writes_enabled else "route"
        # Attribution follows scope: a deployment-wide refusal was not the
        # route's doing, so it claims no prefix.
        prefix = route.prefix if writes_enabled else None
        if route.substrate == "in_memory":
            registry.register_control_port(
                route.prefix,
                _guarded_str(
                    InMemoryControlPort(), read_only=read_only, scope=scope, prefix=prefix
                ),
                is_simulated=route.is_simulated,
            )
        else:
            registry.register_substrate_port(
                route.prefix,
                _guarded_substrate(
                    _build_substrate(route.substrate),
                    read_only=read_only,
                    scope=scope,
                    prefix=prefix,
                ),
                route.substrate,
                is_simulated=route.is_simulated,
            )
    return registry


def _reject_duplicate_prefixes(routes: Sequence[ControlPortRoute]) -> None:
    seen: set[str] = set()
    for route in routes:
        if route.prefix in seen:
            msg = (
                f"CONTROL_PORT_ROUTES declares prefix {route.prefix!r} more than once. "
                "Routes are matched by longest prefix and registration is last-wins, so a "
                "duplicate silently discards the earlier route's substrate and its "
                "is_simulated / read_only declarations. Give each route a distinct prefix."
            )
            raise ValueError(msg)
        seen.add(route.prefix)


def _guarded_str(
    port: ControlPort,
    *,
    read_only: bool,
    scope: Literal["deployment", "route"],
    prefix: str | None = None,
) -> ControlPort:
    """Wrap a `str`-surfaced port in the write guard when writes are off.

    Used for the empty-routes bare `InMemoryControlPort` and for an
    `in_memory` route before `register_control_port` shims it.
    """
    if not read_only:
        return port
    return ReadOnlyControlPort(port, scope=scope, prefix=prefix)


def _guarded_substrate(
    port: SubstrateControlPort[Any],
    *,
    read_only: bool,
    scope: Literal["deployment", "route"],
    prefix: str | None = None,
) -> SubstrateControlPort[Any]:
    """Wrap a typed substrate port in the write guard when writes are off.

    The typed sibling of `_guarded_str`: #568 handed real substrate
    adapters a `ControlAddress` surface, so their guard must take the
    same typed address and refuse before parsing reaches the substrate.
    """
    if not read_only:
        return port
    return ReadOnlySubstratePort(port, scope=scope, prefix=prefix)


def _build_substrate(substrate: Substrate) -> SubstrateControlPort[Any]:
    """Construct the per-substrate typed adapter with deployment defaults.

    Handles the typed-address substrate adapters only; `in_memory` is
    registered through `ControlPortRegistry.register_control_port` in
    `build_control_port` because it is `str`-surfaced.

    Per-adapter constructor kwargs (timeouts, etc.) ride on the
    adapter defaults today; a future iteration may widen
    `ControlPortRoute` with optional per-route overrides
    (`timeout_s`, etc.) when a real deployment surfaces the need.
    """
    if substrate == "epics_ca":
        return EpicsCaControlPort()
    if substrate == "epics_pva":
        return EpicsPvaControlPort()
    return TangoControlPort()


__all__ = ["build_control_port"]
