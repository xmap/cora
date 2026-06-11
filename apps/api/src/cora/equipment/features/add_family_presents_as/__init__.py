"""Vertical slice for the `AddFamilyPresentsAs` command.

Module-as-namespace surface:

    from cora.equipment.features import add_family_presents_as

    cmd = add_family_presents_as.AddFamilyPresentsAs(
        family_id=camera_id, role_id=imager_role_id
    )
    handler = add_family_presents_as.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.add_family_presents_as import tool
from cora.equipment.features.add_family_presents_as.command import AddFamilyPresentsAs
from cora.equipment.features.add_family_presents_as.decider import decide
from cora.equipment.features.add_family_presents_as.handler import Handler, bind
from cora.equipment.features.add_family_presents_as.route import router

__all__ = [
    "AddFamilyPresentsAs",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
