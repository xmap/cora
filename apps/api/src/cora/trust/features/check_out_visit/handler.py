"""Application handler for the `check_out_visit` slice.

Passes the calling principal to the decider as `checked_out_by`, so a caller
can only close its own presence entry.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.check_out_visit.command import CheckOutVisit
from cora.trust.features.check_out_visit.decider import decide


class Handler(Protocol):
    """Callable interface every check_out_visit handler implements."""

    async def __call__(
        self,
        command: CheckOutVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a check_out_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="CheckOutVisit",
        log_prefix="check_out_visit",
        decide_fn=decide,
        actor_kwarg="checked_out_by",
    )
