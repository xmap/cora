"""Vertical slice for the `DefineModel` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.equipment.features import define_model

    cmd = define_model.DefineModel(
        name="Aerotech ANT130-L",
        manufacturer=Manufacturer(name=ManufacturerName("Aerotech")),
        part_number="ANT130-L",
        declared_families=frozenset({rotary_stage_family_id}),
    )
    handler = define_model.bind(deps)
    model_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.equipment.features.define_model import tool
from cora.equipment.features.define_model.command import DefineModel
from cora.equipment.features.define_model.decider import decide
from cora.equipment.features.define_model.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.define_model.route import router

__all__ = [
    "DefineModel",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
