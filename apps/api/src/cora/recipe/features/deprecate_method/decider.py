"""Pure decider for the `DeprecateMethod` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_method but the target is terminal.
Re-deprecating an already-Deprecated method raises (strict-not-
idempotent).

Source-state guard uses tuple-membership (same precedent as
decommission_asset / deprecate_family).

Invariants:
  - State must not be None -> MethodNotFoundError
  - State.status must be in {Defined, Versioned}
    -> MethodCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotDeprecateError,
    MethodDeprecated,
    MethodNotFoundError,
    MethodStatus,
)
from cora.recipe.features.deprecate_method.command import DeprecateMethod

_DEPRECATABLE_STATUSES: tuple[MethodStatus, ...] = (
    MethodStatus.DEFINED,
    MethodStatus.VERSIONED,
)


def decide(
    state: Method | None,
    command: DeprecateMethod,
    *,
    now: datetime,
) -> list[MethodDeprecated]:
    """Decide the events produced by deprecating an existing method."""
    if state is None:
        raise MethodNotFoundError(command.method_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise MethodCannotDeprecateError(state.id, current_status=state.status)
    return [MethodDeprecated(method_id=state.id, reason=command.reason.value, occurred_at=now)]
