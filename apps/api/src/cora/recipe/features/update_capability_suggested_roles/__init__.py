"""Vertical slice for the `UpdateCapabilitySuggestedRoles` command (Layer 3 3E)."""

from cora.recipe.features.update_capability_suggested_roles import tool
from cora.recipe.features.update_capability_suggested_roles.command import (
    UpdateCapabilitySuggestedRoles,
)
from cora.recipe.features.update_capability_suggested_roles.decider import decide
from cora.recipe.features.update_capability_suggested_roles.handler import Handler, bind
from cora.recipe.features.update_capability_suggested_roles.route import router

__all__ = [
    "Handler",
    "UpdateCapabilitySuggestedRoles",
    "bind",
    "decide",
    "router",
    "tool",
]
