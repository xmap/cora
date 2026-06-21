"""Vertical slice for the `HoldProcedure` command.

from cora.operation.features import hold_procedure

cmd = hold_procedure.HoldProcedure(procedure_id=..., reason="...")
handler = hold_procedure.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.hold_procedure import tool
from cora.operation.features.hold_procedure.command import HoldProcedure
from cora.operation.features.hold_procedure.decider import decide
from cora.operation.features.hold_procedure.handler import Handler, bind
from cora.operation.features.hold_procedure.route import router

__all__ = [
    "Handler",
    "HoldProcedure",
    "bind",
    "decide",
    "router",
    "tool",
]
