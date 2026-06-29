"""MCP tool registration for the Campaign BC.

`register_campaign_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `CampaignHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.campaign.features.abandon_campaign import tool as abandon_campaign_tool
from cora.campaign.features.add_run_to_campaign import tool as add_run_to_campaign_tool
from cora.campaign.features.close_campaign import tool as close_campaign_tool
from cora.campaign.features.declare_campaign_steering import tool as declare_campaign_steering_tool
from cora.campaign.features.get_campaign import tool as get_campaign_tool
from cora.campaign.features.hold_campaign import tool as hold_campaign_tool
from cora.campaign.features.list_campaigns import tool as list_campaigns_tool
from cora.campaign.features.register_campaign import tool as register_campaign_tool
from cora.campaign.features.remove_run_from_campaign import tool as remove_run_from_campaign_tool
from cora.campaign.features.resume_campaign import tool as resume_campaign_tool
from cora.campaign.features.start_campaign import tool as start_campaign_tool
from cora.campaign.wire import CampaignHandlers


def register_campaign_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], CampaignHandlers],
) -> None:
    """Register every Campaign slice's MCP tool on the FastMCP server."""
    register_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().register_campaign,
    )
    start_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().start_campaign,
    )
    hold_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().hold_campaign,
    )
    resume_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().resume_campaign,
    )
    close_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().close_campaign,
    )
    abandon_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().abandon_campaign,
    )
    add_run_to_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().add_run_to_campaign,
    )
    remove_run_from_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().remove_run_from_campaign,
    )
    declare_campaign_steering_tool.register(
        mcp,
        get_handler=lambda: get_handlers().declare_campaign_steering,
    )
    get_campaign_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_campaign,
    )
    list_campaigns_tool.register(
        mcp,
        get_handler=lambda: get_handlers().list_campaigns,
    )
