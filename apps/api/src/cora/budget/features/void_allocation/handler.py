"""Application handler for the `void_allocation` slice.

Built on the hoisted `make_allocation_update_handler` factory along
with `amend_allocation_ceiling`. The voiding actor's identity lives
on the event envelope only (the fold records no voided_at timestamp,
so there is no attribution half to stamp), keeping the thin
fold-NEITHER factory. Source set `{Granted, Active}` is enforced by
the decider's guard; the factory is source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.budget._allocation_update_handler import make_allocation_update_handler
from cora.budget.features.void_allocation.command import VoidAllocation
from cora.budget.features.void_allocation.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every void_allocation handler implements."""

    async def __call__(
        self,
        command: VoidAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a void_allocation handler closed over the shared deps."""
    return make_allocation_update_handler(
        deps,
        command_name="VoidAllocation",
        log_prefix="void_allocation",
        decide_fn=decide,
        # Reason length only (not the text): operators searching the log
        # can spot voided envelopes without the log leaking free text.
        extra_log_fields=lambda command: {"reason_length": len(command.reason)},
    )
