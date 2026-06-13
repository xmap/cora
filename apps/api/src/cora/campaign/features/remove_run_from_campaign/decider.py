"""Pure decider for the `RemoveRunFromCampaign` command.

Cross-aggregate decider. Mirrors `add_run_to_campaign`'s shape: takes
a `CampaignMembershipContext` carrying loaded Campaign + Run and
returns BOTH event lists wrapped in `MembershipEvents`.

## Validation order

1. Campaign state must not be None -> `CampaignNotFoundError`
   (defensive; handler raises earlier).
2. Campaign status must be in `{Planned, Active, Held}` ->
   `CampaignCannotRemoveRunError`. Terminal Campaigns refuse
   membership mutation per the design memo lock.
3. Run state must not be None -> `RunNotFoundError` (defensive).
4. Run NOT in `state.run_ids` -> `CampaignRunNotMemberError`.
5. `reason` 1-500 chars after trim ->
   `InvalidCampaignRunRemoveReasonError`.

The handler does NOT separately check `run.campaign_id == command.
campaign_id`: the canonical source of truth for membership is
`Campaign.run_ids`. If a Run somehow carries a stale `campaign_id`
(divergence between the two sides), the projection-enforced
reconciliation invariant catches that elsewhere; this slice rejects
purely on the Campaign-side run_ids check.
"""

from dataclasses import dataclass
from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotRemoveRunError,
    CampaignRunNotMemberError,
    CampaignRunRemoved,
    CampaignStatus,
    InvalidCampaignRunRemoveReasonError,
)
from cora.campaign.features.remove_run_from_campaign.command import RemoveRunFromCampaign
from cora.campaign.features.remove_run_from_campaign.context import CampaignMembershipContext
from cora.run.aggregates.run import RunRemovedFromCampaign
from cora.shared.text_bounds import REASON_MAX_LENGTH

_MEMBERSHIP_ELIGIBLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


@dataclass(frozen=True)
class MembershipEvents:
    """The two event lists produced by a membership removal, one per stream.

    `campaign_events`: appended to the Campaign's stream.
    `run_events`: appended to the Run's stream.

    Both lists are non-empty under normal operation; the handler hands
    them to `EventStore.append_streams` as a single atomic batch.
    """

    campaign_events: list[CampaignRunRemoved]
    run_events: list[RunRemovedFromCampaign]


def decide(
    state: Campaign | None,
    command: RemoveRunFromCampaign,
    *,
    context: CampaignMembershipContext,
    now: datetime,
) -> MembershipEvents:
    """Decide the cross-aggregate events produced by removing a Run.

    Invariants:
      - Campaign status must be Planned, Active, or Held
        -> CampaignCannotRemoveRunError
      - Run must be a member of this Campaign
        -> CampaignRunNotMemberError
      - Reason must be 1-REASON_MAX_LENGTH chars after trim
        -> InvalidCampaignRunRemoveReasonError
    """
    _ = state  # context.campaign carries the same Campaign; signature parity.

    # Context types are non-Optional (handler raises Campaign/RunNotFoundError
    # before constructing the context per the amend_clearance precedent).
    campaign = context.campaign
    if campaign.status not in _MEMBERSHIP_ELIGIBLE_STATUSES:
        raise CampaignCannotRemoveRunError(campaign.id, campaign.status)

    # context.run loaded by handler; not consulted at the decider level
    # because membership is settled by campaign.run_ids set inclusion.
    _ = context.run

    if command.run_id not in campaign.run_ids:
        raise CampaignRunNotMemberError(campaign.id, command.run_id)

    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidCampaignRunRemoveReasonError(command.reason)

    return MembershipEvents(
        campaign_events=[
            CampaignRunRemoved(
                campaign_id=campaign.id,
                run_id=command.run_id,
                reason=trimmed,
                occurred_at=now,
            )
        ],
        run_events=[
            RunRemovedFromCampaign(
                run_id=command.run_id,
                campaign_id=campaign.id,
                reason=trimmed,
                occurred_at=now,
            )
        ],
    )
