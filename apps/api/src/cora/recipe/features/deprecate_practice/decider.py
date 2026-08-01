"""Pure decider for the `DeprecatePractice` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_practice but the target is terminal.
Re-deprecating an already-Deprecated practice raises (strict-not-
idempotent).

Source-state guard uses tuple-membership (same precedent as
deprecate_method / deprecate_family / decommission_asset).

Invariants:
  - State must not be None -> PracticeNotFoundError
  - State.status must be in {Defined, Versioned}
    -> PracticeCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.practice import (
    Practice,
    PracticeCannotDeprecateError,
    PracticeDeprecated,
    PracticeNotFoundError,
    PracticeStatus,
)
from cora.recipe.features.deprecate_practice.command import DeprecatePractice

_DEPRECATABLE_STATUSES: tuple[PracticeStatus, ...] = (
    PracticeStatus.DEFINED,
    PracticeStatus.VERSIONED,
)


def decide(
    state: Practice | None,
    command: DeprecatePractice,
    *,
    now: datetime,
) -> list[PracticeDeprecated]:
    """Decide the events produced by deprecating an existing practice."""
    if state is None:
        raise PracticeNotFoundError(command.practice_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise PracticeCannotDeprecateError(state.id, current_status=state.status)
    return [PracticeDeprecated(practice_id=state.id, reason=command.reason.value, occurred_at=now)]
