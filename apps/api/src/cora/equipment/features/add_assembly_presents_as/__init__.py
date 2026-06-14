"""Vertical slice for the `AddAssemblyPresentsAs` command.

Module-as-namespace surface:

    from cora.equipment.features import add_assembly_presents_as

    cmd = add_assembly_presents_as.AddAssemblyPresentsAs(
        assembly_id=microscope_id, role_id=imager_role_id
    )
    handler = add_assembly_presents_as.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.add_assembly_presents_as import tool
from cora.equipment.features.add_assembly_presents_as.command import AddAssemblyPresentsAs
from cora.equipment.features.add_assembly_presents_as.decider import decide
from cora.equipment.features.add_assembly_presents_as.handler import Handler, bind
from cora.equipment.features.add_assembly_presents_as.route import router

__all__ = [
    "AddAssemblyPresentsAs",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
