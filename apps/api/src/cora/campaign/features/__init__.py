"""Vertical slices owned by the Campaign BC.

Each subdirectory is one slice with the standard six-file shape:
__init__, command (or query), decider (commands only), handler,
route, tool. See `cora.campaign` package docstring for the
module-as-namespace surface.

Slices: the 7 lifecycle (register, get, start, hold, resume, close,
abandon); `list_campaigns` (projection-backed list); the
cross-aggregate membership slices (add_run_to_campaign /
remove_run_from_campaign).
"""

from cora.campaign.features import (
    abandon_campaign,
    add_run_to_campaign,
    close_campaign,
    declare_campaign_steering,
    get_campaign,
    hold_campaign,
    list_campaigns,
    register_campaign,
    remove_run_from_campaign,
    resume_campaign,
    start_campaign,
)

__all__ = [
    "abandon_campaign",
    "add_run_to_campaign",
    "close_campaign",
    "declare_campaign_steering",
    "get_campaign",
    "hold_campaign",
    "list_campaigns",
    "register_campaign",
    "remove_run_from_campaign",
    "resume_campaign",
    "start_campaign",
]
