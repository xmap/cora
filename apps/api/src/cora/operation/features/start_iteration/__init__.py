"""Vertical slice for the `StartProcedureIteration` command.

from cora.operation.features import start_iteration

cmd = start_iteration.StartProcedureIteration(procedure_id=..., iteration_index=1)
handler = start_iteration.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.start_iteration import tool
from cora.operation.features.start_iteration.command import StartProcedureIteration
from cora.operation.features.start_iteration.decider import decide
from cora.operation.features.start_iteration.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.start_iteration.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "StartProcedureIteration",
    "bind",
    "decide",
    "router",
    "tool",
]
