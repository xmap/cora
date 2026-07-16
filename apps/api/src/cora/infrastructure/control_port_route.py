"""Settings-loadable shape for the Operation BC Conductor's per-prefix routing.

The actual `ControlPort` adapter classes live in
`cora.operation.adapters.*` (substrate-specific code) and the
factory that materialises them lives in
`cora.operation.adapters.control_port_config`. This module ONLY
carries the typed config dataclass the `Settings` field uses, so
infrastructure can validate the env var at startup without
importing any BC-specific adapter.

Mirrors the layering used for `IdentityProviderConfig` (the typed
config + validation lives in infrastructure; the auth-side
factories that consume it live in BC + composition-root code).

## Env var shape

The `Settings.control_port_routes` field reads from
`CONTROL_PORT_ROUTES` as a JSON list of objects. Example for a 2-BM
deployment where most PVs are CA but the area-detector image PVs
ride PVA:

    CONTROL_PORT_ROUTES='[
      {"prefix": "2bma:cam1:image", "substrate": "epics_pva"},
      {"prefix": "2bma:", "substrate": "epics_ca"}
    ]'

Empty / unset = the Operation BC's `wire_operation` uses
`InMemoryControlPort` (legacy + test convenience).
"""

from typing import Literal

from pydantic import BaseModel, Field

Substrate = Literal["in_memory", "epics_ca", "epics_pva", "tango"]
"""The closed set of ControlPort substrates a deployment can select.

`in_memory` is the test + opt-out default; `epics_ca` + `epics_pva`
are the production EPICS adapters; `tango` is the PyTango adapter for
Tango-floor deployments (ESRF BLISS, MAX IV). New substrates land here
as additive literal values plus a matching arm in the BC-side
`build_control_port` factory's `_build_substrate` switch.
"""


class ControlPortRoute(BaseModel):
    """One adapter binding in the per-prefix `ControlPortRegistry` routing table.

    `prefix` is the address-string prefix the registry uses for
    longest-prefix-match dispatch. `substrate` selects which adapter
    class the factory will construct for this route. `is_simulated`
    declares that addresses on this route drive a simulator rather
    than real hardware, even when the transport substrate is a real
    one (a soft IOC speaks real Channel Access). It is a declared
    deployment fact, never inferred from `substrate`, and feeds the
    Dataset provenance gate that blocks promoting simulator-origin
    data to Production.

    `read_only` declares that CORA may observe this route but must
    never drive it: `build_control_port` wraps the route's adapter in
    a `ReadOnlyControlPort`, so a write refuses before any substrate
    is contacted. Like `is_simulated` it is a declared deployment
    fact, never inferred from `substrate`.

    `read_only` is per-route EXPRESSIVENESS, for a writable deployment
    that must pin specific prefixes ("CORA may drive the sample stage
    but must never touch the shutter"). It is NOT the safety mechanism
    for an observe-only deployment: it defaults to False, so a route
    that omits it is writable. The deployment-wide safety switch is
    `Settings.control_writes_enabled`, which cannot be partially
    applied. Reach for the switch to make a deployment observe-only;
    reach for this field only to carve a hole in a writable one.
    """

    prefix: str = Field(..., min_length=1)
    substrate: Substrate
    is_simulated: bool = Field(
        default=False,
        description=(
            "True when this route drives a simulator (e.g. a soft IOC) rather "
            "than real hardware. Declared per deployment, not inferred from substrate."
        ),
    )
    read_only: bool = Field(
        default=False,
        description=(
            "True when CORA may read and subscribe on this route but must never "
            "write to it. Refuses before contacting the substrate. Per-route "
            "expressiveness within a writable deployment; to make a whole "
            "deployment observe-only, set CONTROL_WRITES_ENABLED=false instead."
        ),
    )

    model_config = {"extra": "forbid"}


__all__ = ["ControlPortRoute", "Substrate"]
