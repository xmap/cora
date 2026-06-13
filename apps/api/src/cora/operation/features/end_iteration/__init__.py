"""Vertical slice for the `EndProcedureIteration` command.

from cora.operation.features import end_iteration

cmd = end_iteration.EndProcedureIteration(
    procedure_id=..., iteration_index=1, converged=True, reason=None
)
handler = end_iteration.bind(deps)
await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.end_iteration import tool
from cora.operation.features.end_iteration.command import EndProcedureIteration
from cora.operation.features.end_iteration.decider import decide
from cora.operation.features.end_iteration.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.operation.features.end_iteration.route import router

__all__ = [
    "EndProcedureIteration",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
