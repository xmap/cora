"""Pure decider for the `CloseVisitPresence` command.

Requires an open presence entry for the NAMED actor. Does not require any
particular `Visit.status`: the mid-Visit case is the reason this exists, and
closing a lingering entry on an already-terminal Visit is harmless because the
evolver has closed it already, so the guard below simply refuses.

Emits `VisitPresenceClosed`, NOT the `VisitCheckedOut` that `check_out_visit`
emits. The state change is identical and the evolver handles both in one arm,
but the two acts differ in cause, and presence is read as evidence of who was at
a beamline: "did this person leave, or did somebody close their record" has to be
one predicate over the event stream rather than a join against envelope metadata.

Who did the closing is still the envelope's `principal_id` and is deliberately
not duplicated into the payload; under the fold-symmetry convention a `*_by`
field is attribution that would then demand a paired timestamp it does not need.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitActorNotCheckedInError,
    VisitNotFoundError,
    VisitPresenceClosed,
)
from cora.trust.features.close_visit_presence.command import CloseVisitPresence


def decide(
    state: Visit | None,
    command: CloseVisitPresence,
    *,
    now: datetime,
) -> list[VisitPresenceClosed]:
    """Decide events for closing another actor's presence entry.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Named actor must have an open presence entry
        -> VisitActorNotCheckedInError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    open_entry_exists = any(
        e.actor_id == command.actor_id and e.check_out_at is None for e in state.presence_entries
    )
    if not open_entry_exists:
        raise VisitActorNotCheckedInError(visit_id=state.id, actor_id=command.actor_id)
    return [
        VisitPresenceClosed(
            visit_id=state.id,
            actor_id=command.actor_id,
            occurred_at=now,
        )
    ]
