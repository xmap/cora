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
"""

from dataclasses import dataclass
from uuid import UUID

from cora.enclosure.features import register_enclosure
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "enclosure"


@dataclass(frozen=True)
class EnclosureHandlers:
    """The Enclosure BC's handler bundle, each closed over Kernel."""

    register_enclosure: register_enclosure.IdempotentHandler


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
    )
