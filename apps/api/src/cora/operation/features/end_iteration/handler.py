"""Application handler for the `end_iteration` slice.

Update-style handler. Canonical body lives in
`cora.operation._procedure_update_handler.make_procedure_update_handler`;
this module is a thin slice-specific bind. NOT idempotency-wrapped
(transition-style; strict-not-idempotent at the decider, naturally
guarded by event-store optimistic concurrency).

The command's `converged` / `reason` are captured on the emitted
`ProcedureIterationEnded` event payload but are intentionally NOT logged
at the handler boundary (mirrors abort/truncate reason posture), so
this slice does not pass `extra_log_fields`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation._procedure_update_handler import make_procedure_update_handler
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.end_iteration.decider import decide


class Handler(Protocol):
    """Callable interface every end_iteration handler implements."""

    async def __call__(
        self,
        command: EndProcedureIteration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """end_iteration handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: EndProcedureIteration,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an end_iteration handler closed over the shared deps."""
    return make_procedure_update_handler(
        deps,
        command_name="EndProcedureIteration",
        log_prefix="end_iteration",
        decide_fn=decide,
    )
