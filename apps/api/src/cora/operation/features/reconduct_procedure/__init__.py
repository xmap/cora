"""Vertical slice for the `ReconductProcedure` command.

Operator-facing resume-and-replay orchestration: resumes a Held
Procedure and hands control to the `Conductor` runtime, which replays the
pinned step-list tail from the re-establishment boundary (re-drive
setpoints, re-run checks, halt-for-operator on an acquisition), then
auto-completes on a clean tail / aborts on a step failure / leaves
Running on an acquisition halt. Returns a structured
`ReconductProcedureResult`; replay outcomes are encoded in the result,
not raised.

    from cora.operation.features import reconduct_procedure

    cmd = reconduct_procedure.ReconductProcedure(procedure_id=..., re_establishment_boundary=K)
    handler = reconduct_procedure.bind(
        deps, conductor=conductor, resume_procedure=..., complete_procedure=..., abort_procedure=...
    )
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.reconduct_procedure import tool
from cora.operation.features.reconduct_procedure.command import (
    ReconductProcedure,
    ReconductProcedureResult,
)
from cora.operation.features.reconduct_procedure.handler import Handler, bind
from cora.operation.features.reconduct_procedure.route import (
    ReconductProcedureRequest,
    ReconductProcedureResponse,
    router,
)

__all__ = [
    "Handler",
    "ReconductProcedure",
    "ReconductProcedureRequest",
    "ReconductProcedureResponse",
    "ReconductProcedureResult",
    "bind",
    "router",
    "tool",
]
