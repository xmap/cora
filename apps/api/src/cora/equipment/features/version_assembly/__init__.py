"""Vertical slice for the `VersionAssembly` command."""

from cora.equipment.features.version_assembly import tool
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.context import VersionAssemblyContext
from cora.equipment.features.version_assembly.decider import decide
from cora.equipment.features.version_assembly.handler import Handler, bind
from cora.equipment.features.version_assembly.route import router

__all__ = [
    "Handler",
    "VersionAssembly",
    "VersionAssemblyContext",
    "bind",
    "decide",
    "router",
    "tool",
]
