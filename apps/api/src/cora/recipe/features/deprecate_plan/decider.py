"""Pure decider for the `DeprecatePlan` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_plan but the target is terminal.
Re-deprecating an already-Deprecated plan raises (strict-not-
idempotent).

Source-state guard uses tuple-membership (same precedent as
deprecate_practice / deprecate_method / deprecate_family /
decommission_asset).

Invariants:
  - State must not be None -> PlanNotFoundError
  - State.status must be in {Defined, Versioned}
    -> PlanCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotDeprecateError,
    PlanDeprecated,
    PlanNotFoundError,
    PlanStatus,
)
from cora.recipe.features.deprecate_plan.command import DeprecatePlan

_DEPRECATABLE_STATUSES: tuple[PlanStatus, ...] = (
    PlanStatus.DEFINED,
    PlanStatus.VERSIONED,
)


def decide(
    state: Plan | None,
    command: DeprecatePlan,
    *,
    now: datetime,
) -> list[PlanDeprecated]:
    """Decide the events produced by deprecating an existing plan."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise PlanCannotDeprecateError(state.id, current_status=state.status)
    return [PlanDeprecated(plan_id=state.id, reason=command.reason.value, occurred_at=now)]
