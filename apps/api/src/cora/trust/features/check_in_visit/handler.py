"""Application handler for the `check_in_visit` slice.

Passes the calling principal to the decider as `checked_in_by`, so presence
names who actually checked in rather than whoever the caller nominated.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._visit_update_handler import make_visit_update_handler
from cora.trust.features.check_in_visit.command import CheckInVisit
from cora.trust.features.check_in_visit.decider import decide


class Handler(Protocol):
    """Callable interface every check_in_visit handler implements."""

    async def __call__(
        self,
        command: CheckInVisit,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a check_in_visit handler closed over the shared deps."""
    return make_visit_update_handler(
        deps,
        command_name="CheckInVisit",
        log_prefix="check_in_visit",
        decide_fn=decide,
        actor_kwarg="checked_in_by",
    )
