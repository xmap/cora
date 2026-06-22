"""Application handler for the `record_visit_arrival` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.trust._visit_update_handler.make_visit_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.record_visit_arrival.command import RecordVisitArrival
from cora.trust.features.record_visit_arrival.decider import decide


class Handler(Protocol):
    """Callable interface every record_visit_arrival handler implements."""

    async def __call__(
        self,
        command: RecordVisitArrival,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an record_visit_arrival handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="RecordVisitArrival",
        log_prefix="record_visit_arrival",
        decide_fn=decide,
    )
