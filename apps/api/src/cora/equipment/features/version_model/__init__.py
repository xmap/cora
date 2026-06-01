"""Vertical slice for the `VersionModel` command.

Module-as-namespace surface:

    from cora.equipment.features import version_model

    cmd = version_model.VersionModel(
        model_id=...,
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({rotary_stage_family_id}),
        version_tag="v2",
    )
    handler = version_model.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.version_model import tool
from cora.equipment.features.version_model.command import VersionModel
from cora.equipment.features.version_model.decider import decide
from cora.equipment.features.version_model.handler import Handler, bind
from cora.equipment.features.version_model.route import router

__all__ = [
    "Handler",
    "VersionModel",
    "bind",
    "decide",
    "router",
    "tool",
]
