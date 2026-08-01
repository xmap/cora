"""Pure decider for the `DeprecateFamily` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_family but the target is terminal.
Re-deprecating an already-Deprecated family raises (strict-not-
idempotent).

Source-state guard uses tuple-membership (same precedent as
decommission_asset).

Invariants:
  - State must not be None -> FamilyNotFoundError
  - State.status must be in {Defined, Versioned}
    -> FamilyCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.equipment.aggregates.family import (
    Family,
    FamilyCannotDeprecateError,
    FamilyDeprecated,
    FamilyNotFoundError,
    FamilyStatus,
)
from cora.equipment.features.deprecate_family.command import DeprecateFamily

_DEPRECATABLE_STATUSES: tuple[FamilyStatus, ...] = (
    FamilyStatus.DEFINED,
    FamilyStatus.VERSIONED,
)


def decide(
    state: Family | None,
    command: DeprecateFamily,
    *,
    now: datetime,
) -> list[FamilyDeprecated]:
    """Decide the events produced by deprecating an existing family."""
    if state is None:
        raise FamilyNotFoundError(command.family_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise FamilyCannotDeprecateError(state.id, current_status=state.status)
    return [FamilyDeprecated(family_id=state.id, reason=command.reason.value, occurred_at=now)]
