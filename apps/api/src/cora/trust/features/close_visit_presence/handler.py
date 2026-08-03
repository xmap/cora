"""Application handler for the `close_visit_presence` slice.

No `actor_kwarg`: the actor whose entry closes is named by the command, and
the caller reaches the record through the event envelope's `principal_id`.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.close_visit_presence.command import CloseVisitPresence
from cora.trust.features.close_visit_presence.decider import decide


class Handler(Protocol):
    """Callable interface every close_visit_presence handler implements."""

    async def __call__(
        self,
        command: CloseVisitPresence,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a close_visit_presence handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="CloseVisitPresence",
        log_prefix="close_visit_presence",
        decide_fn=decide,
    )
