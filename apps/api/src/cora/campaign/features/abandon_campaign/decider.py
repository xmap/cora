"""Pure decider for the `AbandonCampaign` command.

Multi-source transition: `{Planned, Active, Held} -> Abandoned`.
Strict-not-idempotent (re-abandoning an Abandoned Campaign raises;
Closed also refuses).

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be in `{Planned, Active, Held}` ->
    `CampaignCannotAbandonError`
  - `reason` 1-500 chars after trim ->
    `InvalidCampaignAbandonReasonError`

## NO CASCADE

Per Anti-hooks: `abandon_campaign` writes ONLY to the Campaign
stream. It does NOT modify member Run state. An orchestrated UI
flow may issue separate abort_run commands for each member Run,
but that's a multi-actor decision per Run, not aggregate-level
cascade. Per GLP §10.2.5, ISO 17025 §7.5, 21 CFR §11.10(e).
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignAbandoned,
    CampaignCannotAbandonError,
    CampaignNotFoundError,
    CampaignStatus,
    InvalidCampaignAbandonReasonError,
)
from cora.campaign.features.abandon_campaign.command import AbandonCampaign
from cora.shared.text_bounds import REASON_MAX_LENGTH

_ABANDONABLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


def decide(
    state: Campaign | None,
    command: AbandonCampaign,
    *,
    now: datetime,
) -> list[CampaignAbandoned]:
    """Decide the events produced by abandoning a Campaign.

    Invariants:
      - State must not be None -> CampaignNotFoundError
      - Current status must be Planned, Active, or Held
        -> CampaignCannotAbandonError
      - Reason must be 1-REASON_MAX_LENGTH chars after trim
        -> InvalidCampaignAbandonReasonError
    """
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _ABANDONABLE_STATUSES:
        raise CampaignCannotAbandonError(state.id, state.status)

    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidCampaignAbandonReasonError(command.reason)

    return [
        CampaignAbandoned(
            campaign_id=state.id,
            reason=trimmed,
            occurred_at=now,
        )
    ]
