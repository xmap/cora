"""Vertical slice for the `DeclareCampaignSteering` command."""

from cora.campaign.features.declare_campaign_steering import tool
from cora.campaign.features.declare_campaign_steering.command import DeclareCampaignSteering
from cora.campaign.features.declare_campaign_steering.decider import decide
from cora.campaign.features.declare_campaign_steering.handler import Handler, bind
from cora.campaign.features.declare_campaign_steering.route import router

__all__ = [
    "DeclareCampaignSteering",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
