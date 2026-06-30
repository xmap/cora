"""The `DeclareCampaignSteering` command -- intent dataclass for this slice.

Declares the Campaign's steering INTENT: an objective (what good means)
plus a search space (where a future across-Run steerer may look). PUT
semantics: a re-declare overwrites the prior intent wholesale. Allowed
from Planned or Active only (not on Held / Closed / Abandoned).

The declaring actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.steering import SteeringObjective, SteeringSpace


@dataclass(frozen=True)
class DeclareCampaignSteering:
    """Declare a Campaign's steering INTENT (objective + search space)."""

    campaign_id: UUID
    objective: SteeringObjective
    space: SteeringSpace
