"""The `ReactivateActor` command, intent dataclass for this slice.

`actor_id` is the **target** Actor aggregate (caller-supplied: the actor
to return to service). The principal-id of the invoker is supplied
separately by the application handler at call time, not in the command.

The inverse of `DeactivateActor`, and reserved by that slice's route
docstring before this one was built. No `reason` field: deactivation
carries none either, and the pair stays symmetric.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReactivateActor:
    """Return a deactivated actor to service by id."""

    actor_id: UUID
