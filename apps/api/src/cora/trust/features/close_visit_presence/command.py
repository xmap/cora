"""The `CloseVisitPresence` command -- intent dataclass.

Closes ANOTHER actor's open presence entry. This is the deliberate
counterpart to `CheckOutVisit`, which closes only the caller's own.

The two are separate commands, not one command with a nullable actor, so
that closing somebody else's record needs its own Policy grant. Somebody
who forgot to check out and went home leaves an entry that only this
command can close while the Visit is still running; once the Visit reaches
a terminal state the evolver closes every open entry anyway, so this exists
for the mid-Visit case.

Attribution is the event envelope's, not a payload field: the envelope
already carries `principal_id` and `command_name`, so a `VisitCheckedOut`
recorded under `CloseVisitPresence` is distinguishable from a self-checkout
without duplicating the caller into the payload.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CloseVisitPresence:
    """Close `actor_id`'s currently-open presence entry on the Visit."""

    visit_id: UUID
    actor_id: UUID
