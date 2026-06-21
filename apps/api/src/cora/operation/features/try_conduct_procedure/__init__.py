"""Vertical slice for the `TryConductProcedure` command.

Pause-capable conduct: the conduct verb-family's third member (conduct =
run-to-terminal, reconduct = resume-and-replay, try-conduct =
pause-to-Held-on-recoverable-failure). Hands control to the `Conductor`
runtime which, on a recoverable step failure, pauses the Procedure to `Held`
instead of aborting it, so an operator can `reconduct` from the pinned
resolved steps. Returns a structured `TryConductProcedureResult` whose `held`
flag distinguishes a paused (resumable) outcome from a terminal one.

    from cora.operation.features import try_conduct_procedure

    cmd = try_conduct_procedure.TryConductProcedure(procedure_id=..., steps=(...))
    handler = try_conduct_procedure.bind(deps, conductor=conductor, expansion_port=...)
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.try_conduct_procedure import tool
from cora.operation.features.try_conduct_procedure.command import (
    TryConductProcedure,
    TryConductProcedureResult,
)
from cora.operation.features.try_conduct_procedure.handler import Handler, bind
from cora.operation.features.try_conduct_procedure.route import (
    TryConductProcedureRequest,
    TryConductProcedureResponse,
    router,
)

__all__ = [
    "Handler",
    "TryConductProcedure",
    "TryConductProcedureRequest",
    "TryConductProcedureResponse",
    "TryConductProcedureResult",
    "bind",
    "router",
    "tool",
]
