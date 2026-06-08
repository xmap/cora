"""Pure decider for the `DecommissionFacility` command.

Terminal transition: Active -> Decommissioned. Strict-not-idempotent:
re-decommissioning an already-Decommissioned facility raises
`FacilityCannotDecommissionError` (HTTP 409) per the same convention
as `revoke_credential` / `revoke_permit`.

`decommissioned_by` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`FacilityDecommissioned` event for the fold-symmetric attribution
denorm.

## Validation

  - State must not be None (facility must exist)
    -> FacilityNotFoundError
  - Current status must be Active (not Decommissioned)
    -> FacilityCannotDecommissionError
"""

from datetime import datetime

from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotDecommissionError,
    FacilityDecommissioned,
    FacilityNotFoundError,
    FacilityStatus,
)
from cora.federation.features.decommission_facility.command import DecommissionFacility
from cora.shared.identity import ActorId


def decide(
    state: Facility | None,
    command: DecommissionFacility,
    *,
    now: datetime,
    decommissioned_by: ActorId,
) -> list[FacilityDecommissioned]:
    """Decide the events produced by decommissioning a Facility.

    Invariants:
      - State must not be None -> FacilityNotFoundError
      - Current status must be Active
        -> FacilityCannotDecommissionError
    """
    if state is None:
        raise FacilityNotFoundError(command.facility_id)
    if state.status is not FacilityStatus.ACTIVE:
        raise FacilityCannotDecommissionError(state.id)

    return [
        FacilityDecommissioned(
            facility_id=state.id,
            decommissioned_by=decommissioned_by,
            occurred_at=now,
            reason=command.reason,
        )
    ]


__all__ = ["decide"]
