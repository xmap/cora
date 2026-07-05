"""Pure decider for the `DenyRatification` command.

Single-source transition: Requested -> Denied. Strict-not-idempotent. Reason is
mandatory and validated 1-500 chars after trim.

The refusing principal `denied_by` is threaded in by the handler from the
envelope `principal_id`, and the same independence invariant as grant applies:
the denier must differ from the requester. Kind-blind: compares bare principal
identifiers, never actor kind.
"""

from datetime import datetime
from uuid import UUID

from cora.shared.text_bounds import REASON_MAX_LENGTH
from cora.trust.aggregates.ratification import (
    InvalidRatificationReasonError,
    Ratification,
    RatificationCannotDenyError,
    RatificationDenied,
    RatificationNotFoundError,
    RatificationRequesterCannotSelfRatifyError,
    RatificationStatus,
)
from cora.trust.features.deny_ratification.command import DenyRatification

_PERMITTED: tuple[RatificationStatus, ...] = (RatificationStatus.REQUESTED,)


def decide(
    state: Ratification | None,
    command: DenyRatification,
    *,
    denied_by: UUID,
    now: datetime,
) -> list[RatificationDenied]:
    """Decide events for denying a Requested ratification.

    Invariants:
      - State must not be None -> RatificationNotFoundError
      - Status must be Requested -> RatificationCannotDenyError
      - Denier must differ from the requester (independence / four-eyes)
        -> RatificationRequesterCannotSelfRatifyError
      - Reason 1-500 chars after trim -> InvalidRatificationReasonError
    """
    if state is None:
        raise RatificationNotFoundError(command.ratification_id)
    if state.status not in _PERMITTED:
        raise RatificationCannotDenyError(
            ratification_id=state.id,
            current_status=state.status,
        )
    if denied_by == state.requested_by:
        raise RatificationRequesterCannotSelfRatifyError(
            ratification_id=state.id,
            principal_id=denied_by,
        )
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidRatificationReasonError(command.reason)
    return [RatificationDenied(ratification_id=state.id, reason=trimmed, occurred_at=now)]
