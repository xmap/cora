"""Vertical slice for the `DefineAssembly` command."""

from cora.equipment.features.define_assembly import tool
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.context import DefineAssemblyContext
from cora.equipment.features.define_assembly.decider import decide
from cora.equipment.features.define_assembly.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.define_assembly.route import router

__all__ = [
    "DefineAssembly",
    "DefineAssemblyContext",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
