"""Compose the Enclosure BC's handlers from `Kernel`.

`wire_enclosure(deps)` is invoked once from the FastAPI lifespan and
the returned `EnclosureHandlers` bundle is stored on
`app.state.enclosure`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `EnclosureHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Supply / Trust /
Subject / Equipment (composition order matters, innermost first):

1. `bind(deps)`, bare handler.
2. `with_idempotency` (create-style commands only), Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing`, OTel span around every handler call. Records
   `cora.bc`, `cora.command` attributes.

## Wired handlers

  - `register_enclosure` (create-style; idempotency-wrapped)
  - `observe_enclosure_status` (Monitor-trigger transition; no
    idempotency wrap, mirrors Supply `observe_supply_status`. The
    monitor_ref carried on the event payload is the natural dedup
    key, and the status-change-only short-circuit in the decider
    silently absorbs re-emission of identical-status observations.)
  - `decommission_enclosure` (lifecycle-terminal transition; no
    idempotency wrap, mirrors Federation `decommission_facility` and
    Supply `deregister_supply`. Strict-not-idempotent: re-decommissioning
    raises `EnclosureCannotDecommissionError` -> HTTP 409, so
    HTTP-layer caching adds no value.)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.enclosure.features import (
    decommission_enclosure,
    observe_enclosure_status,
    register_enclosure,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "enclosure"


@dataclass(frozen=True)
class EnclosureHandlers:
    """The Enclosure BC's handler bundle, each closed over Kernel."""

    register_enclosure: register_enclosure.IdempotentHandler
    observe_enclosure_status: observe_enclosure_status.Handler
    decommission_enclosure: decommission_enclosure.Handler


def wire_enclosure(deps: Kernel) -> EnclosureHandlers:
    """Build the Enclosure BC handlers from shared dependencies."""
    return EnclosureHandlers(
        register_enclosure=with_tracing(
            with_idempotency(
                register_enclosure.bind(deps),
                deps.idempotency_store,
                command_name="RegisterEnclosure",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterEnclosure",
            bc=_BC,
        ),
        observe_enclosure_status=with_tracing(
            observe_enclosure_status.bind(deps),
            command_name="ObserveEnclosureStatus",
            bc=_BC,
        ),
        decommission_enclosure=with_tracing(
            decommission_enclosure.bind(deps),
            command_name="DecommissionEnclosure",
            bc=_BC,
        ),
    )
