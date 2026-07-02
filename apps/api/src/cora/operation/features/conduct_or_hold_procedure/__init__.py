"""Vertical slice for the `ConductOrHoldProcedure` command.

Pause-capable conduct: the conduct verb-family's third member (conduct =
run-to-terminal, conduct_from = resume-and-replay, conduct-or-hold =
pause-to-Held-on-recoverable-failure). Hands control to the `Conductor`
runtime which, on a recoverable step failure, pauses the Procedure to `Held`
instead of aborting it, so an operator can `conduct_from` from the pinned
resolved steps. Returns a structured `ConductOrHoldProcedureResult` whose `held`
flag distinguishes a paused (resumable) outcome from a terminal one.

    from cora.operation.features import conduct_or_hold_procedure

    cmd = conduct_or_hold_procedure.ConductOrHoldProcedure(procedure_id=..., steps=(...))
    handler = conduct_or_hold_procedure.bind(deps, conductor=conductor, expansion_port=...)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_or_hold_procedure import tool
from cora.operation.features.conduct_or_hold_procedure.command import (
    ConductOrHoldProcedure,
    ConductOrHoldProcedureResult,
)
from cora.operation.features.conduct_or_hold_procedure.handler import Handler, bind
from cora.operation.features.conduct_or_hold_procedure.route import (
    ConductOrHoldProcedureRequest,
    ConductOrHoldProcedureResponse,
    router,
)

__all__ = [
    "ConductOrHoldProcedure",
    "ConductOrHoldProcedureRequest",
    "ConductOrHoldProcedureResponse",
    "ConductOrHoldProcedureResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
