"""Application handler for the `amend_allocation_ceiling` slice.

Built on the hoisted `make_allocation_update_handler` factory along
with `void_allocation`. The amending actor's identity lives on the
event envelope only (no fold-symmetry pair for the amendment, which
records no timestamp on state), so the thin fold-NEITHER factory
applies. Source set `{Granted, Active}` is enforced by the decider's
guard; the factory is source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.budget._allocation_update_handler import make_allocation_update_handler
from cora.budget.features.amend_allocation_ceiling.command import AmendAllocationCeiling
from cora.budget.features.amend_allocation_ceiling.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every amend_allocation_ceiling handler implements."""

    async def __call__(
        self,
        command: AmendAllocationCeiling,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an amend_allocation_ceiling handler closed over the shared deps."""
    return make_allocation_update_handler(
        deps,
        command_name="AmendAllocationCeiling",
        log_prefix="amend_allocation_ceiling",
        decide_fn=decide,
        extra_log_fields=lambda command: {"ceiling_usd": command.ceiling_usd},
    )
