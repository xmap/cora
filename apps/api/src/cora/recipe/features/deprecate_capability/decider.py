"""Pure decider for the `DeprecateCapability` command.

Multi-source-state transition: `Defined | Versioned -> Deprecated`.
Re-deprecating a Deprecated Capability raises (strict-not-idempotent).

`replaced_by_capability_id` (when supplied) points at a successor
Capability. Eventual-consistency: the target id is NOT verified
cross-stream at decider time (same precedent as Method.needed_family_ids).

Invariants:
  - State must not be None -> CapabilityNotFoundError
  - State.status must be in {Defined, Versioned}
    -> CapabilityCannotDeprecateError(current_status=...)
"""

from datetime import datetime

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotDeprecateError,
    CapabilityDeprecated,
    CapabilityNotFoundError,
    CapabilityStatus,
)
from cora.recipe.features.deprecate_capability.command import DeprecateCapability

_DEPRECATABLE_STATUSES: tuple[CapabilityStatus, ...] = (
    CapabilityStatus.DEFINED,
    CapabilityStatus.VERSIONED,
)


def decide(
    state: Capability | None,
    command: DeprecateCapability,
    *,
    now: datetime,
) -> list[CapabilityDeprecated]:
    """Decide the events produced by deprecating an existing Capability."""
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)
    if state.status not in _DEPRECATABLE_STATUSES:
        raise CapabilityCannotDeprecateError(state.id, current_status=state.status)
    return [
        CapabilityDeprecated(
            capability_id=state.id,
            reason=command.reason.value,
            replaced_by_capability_id=command.replaced_by_capability_id,
            occurred_at=now,
        )
    ]
