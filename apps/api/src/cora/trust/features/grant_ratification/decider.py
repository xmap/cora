"""Pure decider for the `GrantRatification` command.

Single-source transition: Requested -> Granted. Strict-not-idempotent.

The co-signing principal `granted_by` is threaded in by the handler from the
envelope `principal_id`. The independence invariant, the four-eyes property the
consequence gate exists to provide, is enforced here: the grantor must differ
from the requester. Kind-blind: the check compares bare principal identifiers and
never reads actor kind, so a human co-signs for an agent (and vice versa)
identically.
"""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.ratification import (
    Ratification,
    RatificationCannotGrantError,
    RatificationGranted,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
)
from cora.trust.features.grant_ratification.command import GrantRatification

_PERMITTED: tuple[RatificationStatus, ...] = (RatificationStatus.REQUESTED,)


def decide(
    state: Ratification | None,
    command: GrantRatification,
    *,
    granted_by: UUID,
    now: datetime,
) -> list[RatificationGranted]:
    """Decide events for granting a Requested ratification.

    Invariants:
      - State must not be None -> RatificationNotFoundError
      - Status must be Requested -> RatificationCannotGrantError
      - Grantor must differ from the requester (independence / four-eyes)
        -> RatificationRequesterCannotSelfRatifyError
    """
    if state is None:
        raise RatificationNotFoundError(command.ratification_id)
    if state.status not in _PERMITTED:
        raise RatificationCannotGrantError(
            ratification_id=state.id,
            current_status=state.status,
        )
    if granted_by == state.requested_by:
        raise RatificationRequesterCannotSelfRatifyError(
            ratification_id=state.id,
            principal_id=granted_by,
        )
    return [RatificationGranted(ratification_id=state.id, occurred_at=now)]
