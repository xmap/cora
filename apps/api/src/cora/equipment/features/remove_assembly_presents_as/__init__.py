"""Vertical slice for the `RemoveAssemblyPresentsAs` command."""

from cora.equipment.features.remove_assembly_presents_as import tool
from cora.equipment.features.remove_assembly_presents_as.command import (
    RemoveAssemblyPresentsAs,
)
from cora.equipment.features.remove_assembly_presents_as.decider import decide
from cora.equipment.features.remove_assembly_presents_as.handler import Handler, bind
from cora.equipment.features.remove_assembly_presents_as.route import router

__all__ = [
    "Handler",
    "RemoveAssemblyPresentsAs",
    "bind",
    "decide",
    "router",
    "tool",
]
