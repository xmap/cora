"""Application handler for the `activate_allocation` slice.

Built on the actor-stamping `make_allocation_actor_update_handler`
factory: the fold records `(activated_at, activated_by)` per
[[project_fold_symmetry_design]], so the handler threads the
envelope's `principal_id` into the decider as `activated_by`.
Single-source from Granted; the decider's guard enforces this, the
factory is source-set-agnostic.
"""

from typing import Protocol
from uuid import UUID

from cora.budget._allocation_update_handler import make_allocation_actor_update_handler
from cora.budget.features.activate_allocation.command import ActivateAllocation
from cora.budget.features.activate_allocation.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every activate_allocation handler implements."""

    async def __call__(
        self,
        command: ActivateAllocation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an activate_allocation handler closed over the shared deps."""
    return make_allocation_actor_update_handler(
        deps,
        command_name="ActivateAllocation",
        log_prefix="activate_allocation",
        decide_fn=decide,
        actor_kwarg="activated_by",
    )
