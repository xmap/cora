"""Operation BC factory: materialise a `ControlPort` from deployment routes.

`build_control_port(routes)` consumes the typed
`list[ControlPortRoute]` carried on `Settings.control_port_routes`
and returns either:

  - `InMemoryControlPort` (empty list / no env var set; legacy default
    + test convenience; preserves the v1 wire-up behavior for tests +
    deployments that have not yet opted in to a substrate)
  - `ControlPortRegistry` populated with the configured substrate
    adapters per prefix (longest-prefix match dispatch, per
    `cora.operation.adapters.control_port_registry`)

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

## Lifecycle

The returned port owns the lifecycle of every adapter it constructs:
`aclose()` on the returned port fans out to each adapter (registry
path) or is a no-op (in-memory path). The caller (`wire_operation`)
does NOT track individual adapters.
"""

from collections.abc import Sequence
from typing import Any

from cora.infrastructure.control_port_route import ControlPortRoute, Substrate
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.tango_control_port import TangoControlPort
from cora.operation.ports.control_port import ControlPort, SubstrateControlPort


def build_control_port(routes: Sequence[ControlPortRoute]) -> ControlPort:
    """Materialise the ControlPort the Conductor talks to.

    Empty routes returns a single `InMemoryControlPort` (legacy
    default + test convenience). Non-empty routes returns a
    `ControlPortRegistry` populated with the configured substrate
    adapters per prefix. `in_memory` routes go through
    `register_control_port` (the registry wraps the `str`-surfaced adapter);
    the real substrate adapters register directly on the typed surface.
    """
    if not routes:
        return InMemoryControlPort()
    registry = ControlPortRegistry()
    for route in routes:
        if route.substrate == "in_memory":
            registry.register_control_port(
                route.prefix, InMemoryControlPort(), is_simulated=route.is_simulated
            )
        else:
            registry.register_substrate_port(
                route.prefix,
                _build_substrate(route.substrate),
                route.substrate,
                is_simulated=route.is_simulated,
            )
    return registry


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
