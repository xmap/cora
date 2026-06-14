"""Application handler for the `start_iteration` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind. NOT idempotency-wrapped
(transition-style; strict-not-idempotent at the decider, naturally
guarded by event-store optimistic concurrency), mirroring
complete/abort/truncate.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_iteration.decider import decide


class Handler(Protocol):
    """Callable interface every start_iteration handler implements."""

    async def __call__(
        self,
        command: StartProcedureIteration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """start_iteration handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: StartProcedureIteration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_iteration handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="StartProcedureIteration",
        log_prefix="start_iteration",
        decide_fn=decide,
    )
