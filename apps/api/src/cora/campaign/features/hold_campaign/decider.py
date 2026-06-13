"""Pure decider for the `HoldCampaign` command.

Single-source transition: `Active -> Held`. Strict-not-idempotent
(re-holding an already-Held Campaign raises). Reason is mandatory.

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be `Active` -> `CampaignCannotHoldError`
  - `reason` 1-500 chars after trim -> `InvalidCampaignHoldReasonError`
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotHoldError,
    CampaignHeld,
    CampaignNotFoundError,
    CampaignStatus,
    InvalidCampaignHoldReasonError,
)
from cora.campaign.features.hold_campaign.command import HoldCampaign
from cora.shared.text_bounds import REASON_MAX_LENGTH

_HOLDABLE_STATUSES: tuple[CampaignStatus, ...] = (CampaignStatus.ACTIVE,)


def decide(
    state: Campaign | None,
    command: HoldCampaign,
    *,
    now: datetime,
) -> list[CampaignHeld]:
    """Decide the events produced by holding an Active Campaign.

    Invariants:
      - State must not be None -> CampaignNotFoundError
      - Current status must be Active -> CampaignCannotHoldError
      - Reason must be 1-REASON_MAX_LENGTH chars after trim
        -> InvalidCampaignHoldReasonError
    """
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _HOLDABLE_STATUSES:
        raise CampaignCannotHoldError(state.id, state.status)

    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidCampaignHoldReasonError(command.reason)

    return [
        CampaignHeld(
            campaign_id=state.id,
            reason=trimmed,
            occurred_at=now,
        )
    ]
