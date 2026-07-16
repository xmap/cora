"""The `GrantAllocation` command -- intent dataclass for this slice.

Carries the caller-controlled fields for one spending envelope: the
USD ceiling, the operator-facing note, and an optional
`campaign_id` that binds the award window to a Campaign's lifecycle
(the CampaignClosed subscriber seals a campaign-bound
envelope beside the campaign's own books).

`allocation_id` is optional. None (the default) keeps the
`define_language_model` posture: the handler mints a UUIDv7 via the
injected IdGenerator port. A caller-supplied id serves deployments
that stand envelopes up from configuration and need stable ids across
environments; the handler loads that stream before deciding so the
genesis guard can reject a collision.

The granting actor's identity is injected by the handler from the
envelope's `principal_id` (the decider's `granted_by` kwarg, per the
fold-symmetry attribution rule); no actor field on the command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GrantAllocation:
    """Grant a new spending envelope (lands in Granted, dormant)."""

    ceiling_usd: float
    note: str
    campaign_id: UUID | None = None
    allocation_id: UUID | None = None
