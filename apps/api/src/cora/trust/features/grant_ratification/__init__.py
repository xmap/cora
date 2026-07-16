"""Vertical slice for the `GrantRatification` command."""

from cora.trust.features.grant_ratification import tool
from cora.trust.features.grant_ratification.command import GrantRatification
from cora.trust.features.grant_ratification.decider import decide
from cora.trust.features.grant_ratification.handler import Handler, bind
from cora.trust.features.grant_ratification.route import router

__all__ = ["GrantRatification", "Handler", "bind", "decide", "router", "tool"]
