"""Pure decider for the `CheckOutVisit` command.

Requires an open presence entry for the CALLING principal on the Visit. Does NOT
require any particular `Visit.status` -- checking out of a terminal Visit is
permitted, so somebody who forgot to check out before the Visit completed can
still close their own entry afterwards. Closing SOMEBODY ELSE'S lingering entry
is no longer possible here and has no replacement slice yet; see the command
docstring. The frozen-replace pattern in the evolver lifts the entry's
`check_out_at` from None to `now`.
"""

from datetime import datetime

from cora.shared.identity import ActorId
from cora.trust.aggregates.visit import (
    Visit,
    VisitActorNotCheckedInError,
    VisitCheckedOut,
    VisitNotFoundError,
)
from cora.trust.features.check_out_visit.command import CheckOutVisit


def decide(
    state: Visit | None,
    command: CheckOutVisit,
    *,
    now: datetime,
    checked_out_by: ActorId,
) -> list[VisitCheckedOut]:
    """Decide events for checking the calling principal out of a Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Caller must have an open presence entry
        -> VisitActorNotCheckedInError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    open_entry_exists = any(
        e.actor_id == checked_out_by and e.check_out_at is None for e in state.presence_entries
    )
    if not open_entry_exists:
        raise VisitActorNotCheckedInError(visit_id=state.id, actor_id=checked_out_by)
    return [
        VisitCheckedOut(
            visit_id=state.id,
            actor_id=checked_out_by,
            occurred_at=now,
        )
    ]
