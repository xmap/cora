"""Pure decider for the `DeprecateModel` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Same source-set as version_model but the target is terminal.
Re-deprecating an already-Deprecated model raises (strict-not-
idempotent; mirrors deprecate_family).

Source-state guard uses tuple-membership (same precedent as
deprecate_family and version_model). The decider validates the
bounded-text `reason` defensively via `ModelDeprecationReason` so
direct in-process callers get the same protection as API-boundary
callers.

Once Deprecated, no further `ModelVersioned`, `ModelFamilyAdded`, or
`ModelFamilyRemoved` events are accepted (enforced by the relevant
deciders via their own source-state guards). Existing Assets bound to
the Model continue to function; deprecation is an authoring signal,
not a runtime gate.

Invariants:
  - State must not be None -> ModelNotFoundError
  - State.status must be in {Defined, Versioned}
    -> ModelCannotDeprecateError(current_status=...)
  - reason must be valid -> InvalidModelDeprecationReasonError
    (via ModelDeprecationReason VO)
"""

from datetime import datetime

from cora.equipment.aggregates.model import (
    Model,
    ModelCannotDeprecateError,
    ModelDeprecated,
    ModelDeprecationReason,
    ModelNotFoundError,
    ModelStatus,
)
from cora.equipment.features.deprecate_model.command import DeprecateModel

_DEPRECATABLE_STATUSES: tuple[ModelStatus, ...] = (
    ModelStatus.DEFINED,
    ModelStatus.VERSIONED,
)


def decide(
    state: Model | None,
    command: DeprecateModel,
    *,
    now: datetime,
) -> list[ModelDeprecated]:
    """Decide the events produced by deprecating an existing model."""
    if state is None:
        raise ModelNotFoundError(command.model_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise ModelCannotDeprecateError(state.id, current_status=state.status)
    reason = ModelDeprecationReason(command.reason)
    return [
        ModelDeprecated(
            model_id=state.id,
            reason=reason.value,
            occurred_at=now,
        )
    ]
