"""Vertical slice for the `RemoveFamilyPresentsAs` command."""

from cora.equipment.features.remove_family_presents_as import tool
from cora.equipment.features.remove_family_presents_as.command import (
    RemoveFamilyPresentsAs,
)
from cora.equipment.features.remove_family_presents_as.decider import decide
from cora.equipment.features.remove_family_presents_as.handler import Handler, bind
from cora.equipment.features.remove_family_presents_as.route import router

__all__ = [
    "Handler",
    "RemoveFamilyPresentsAs",
    "bind",
    "decide",
    "router",
    "tool",
]
