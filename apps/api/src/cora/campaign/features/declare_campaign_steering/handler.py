"""Application handler for the `declare_campaign_steering` slice.

Update-style handler. Body lives in the per-aggregate factory at
`cora.campaign._campaign_update_handler.make_campaign_update_handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.campaign._campaign_update_handler import make_campaign_update_handler
from cora.campaign.features.declare_campaign_steering.command import DeclareCampaignSteering
from cora.campaign.features.declare_campaign_steering.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every declare_campaign_steering handler implements."""

    async def __call__(
        self,
        command: DeclareCampaignSteering,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a declare_campaign_steering handler closed over the shared deps."""
    return make_campaign_update_handler(
        deps,
        command_name="DeclareCampaignSteering",
        log_prefix="declare_campaign_steering",
        decide_fn=decide,
    )
