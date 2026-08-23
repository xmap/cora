"""Compose the Supply BC's handlers from `Kernel`.

`wire_supply(deps)` is invoked once from the FastAPI lifespan and
the returned `SupplyHandlers` bundle is stored on
`app.state.supply`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `SupplyHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

## Wired handlers

  - `register_supply` (create-style; idempotency-wrapped)
  - `mark_supply_available` (transition)
  - `degrade_supply` (transition)
  - `mark_supply_unavailable` (transition)
  - `mark_supply_recovering` (transition)
  - `restore_supply` (transition)
  - `deregister_supply` (lifecycle-terminal transition)
  - `get_supply` (query)
  - `list_supplies` (query)

The bundle also carries `probe_store` (not a handler; see its own
docstring on `SupplyHandlers`).

All six transition handlers are built via the
`make_supply_update_handler` factory (hoisted at the
rule-of-three trigger; mirrors `_asset_update_handler`).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.supply.aggregates.supply import (
    InMemorySupplyProbeStore,
    PostgresSupplyProbeStore,
    SupplyProbeStore,
)
from cora.supply.features import (
    degrade_supply,
    deregister_supply,
    get_supply,
    list_supplies,
    mark_supply_available,
    mark_supply_recovering,
    mark_supply_unavailable,
    observe_supply_status,
    register_supply,
    restore_supply,
)

_BC = "supply"


@dataclass(frozen=True)
class SupplyHandlers:
    """The Supply BC's handler bundle, each closed over Kernel.

    Six transition handlers (mark_available + degrade +
    mark_unavailable + mark_recovering + restore + deregister)
    plus register_supply (create-style; idempotency-wrapped) plus
    two queries (get_supply, list_supplies). Every transition
    handler flows through `make_supply_update_handler`, hoisted at
    the rule-of-three trigger.
    """

    register_supply: register_supply.IdempotentHandler
    mark_supply_available: mark_supply_available.Handler
    degrade_supply: degrade_supply.Handler
    mark_supply_unavailable: mark_supply_unavailable.Handler
    mark_supply_recovering: mark_supply_recovering.Handler
    restore_supply: restore_supply.Handler
    deregister_supply: deregister_supply.Handler
    observe_supply_status: observe_supply_status.Handler
    get_supply: get_supply.Handler
    list_supplies: list_supplies.Handler
    probe_store: SupplyProbeStore
    """The Supply-probe trail's write store. Surfaced on the bundle, not
    a handler, mirroring `EnclosureHandlers.permit_probe_store`: the
    FastAPI lifespan needs it at `supply_status_monitor_lifespan`'s call
    site, a dependency that isn't itself a command handler."""


def wire_supply(deps: Kernel) -> SupplyHandlers:
    """Build the Supply BC handlers from shared dependencies."""
    probe_store: SupplyProbeStore = (
        PostgresSupplyProbeStore(deps.pool) if deps.pool is not None else InMemorySupplyProbeStore()
    )
    return SupplyHandlers(
        probe_store=probe_store,
        register_supply=with_tracing(
            with_idempotency(
                register_supply.bind(deps),
                deps.idempotency_store,
                command_name="RegisterSupply",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterSupply",
            bc=_BC,
        ),
        mark_supply_available=with_tracing(
            mark_supply_available.bind(deps),
            command_name="MarkSupplyAvailable",
            bc=_BC,
        ),
        degrade_supply=with_tracing(
            degrade_supply.bind(deps),
            command_name="DegradeSupply",
            bc=_BC,
        ),
        mark_supply_unavailable=with_tracing(
            mark_supply_unavailable.bind(deps),
            command_name="MarkSupplyUnavailable",
            bc=_BC,
        ),
        mark_supply_recovering=with_tracing(
            mark_supply_recovering.bind(deps),
            command_name="MarkSupplyRecovering",
            bc=_BC,
        ),
        restore_supply=with_tracing(
            restore_supply.bind(deps),
            command_name="RestoreSupply",
            bc=_BC,
        ),
        deregister_supply=with_tracing(
            deregister_supply.bind(deps),
            command_name="DeregisterSupply",
            bc=_BC,
        ),
        observe_supply_status=with_tracing(
            observe_supply_status.bind(deps),
            command_name="ObserveSupplyStatus",
            bc=_BC,
        ),
        get_supply=with_tracing(
            get_supply.bind(deps),
            command_name="GetSupply",
            bc=_BC,
            kind="query",
        ),
        list_supplies=with_tracing(
            list_supplies.bind(deps),
            command_name="ListSupplies",
            bc=_BC,
            kind="query",
        ),
    )
