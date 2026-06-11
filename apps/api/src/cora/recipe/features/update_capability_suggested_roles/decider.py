"""Pure decider for `update_capability_suggested_roles`.

Layer 3 sub-slice 3E. Wholesale-replace shape (Pattern P), restricted
to Defined + Versioned statuses. Per memo Lock 10: documentation-only,
NOT fitness-enforced -- the decider does not gate Method authoring.
"""

from datetime import datetime

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotUpdateSuggestedRolesError,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilitySuggestedRolesUpdated,
)
from cora.recipe.features.update_capability_suggested_roles.command import (
    UpdateCapabilitySuggestedRoles,
)


def decide(
    state: Capability | None,
    command: UpdateCapabilitySuggestedRoles,
    *,
    now: datetime,
) -> list[CapabilitySuggestedRolesUpdated]:
    """Decide the events produced by updating suggested_role_ids.

    Invariants:
      - State must not be None -> CapabilityNotFoundError
      - Status must be Defined or Versioned (Deprecated rejects) ->
        CapabilityCannotUpdateSuggestedRolesError
    """
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)

    if state.status is CapabilityStatus.DEPRECATED:
        raise CapabilityCannotUpdateSuggestedRolesError(
            capability_id=state.id,
            current_status=state.status,
        )

    return [
        CapabilitySuggestedRolesUpdated(
            capability_id=state.id,
            suggested_role_ids=command.suggested_role_ids,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
