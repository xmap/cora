"""Vertical slice for the `ConductFromProcedure` command.

Operator-facing resume-and-replay orchestration: resumes a Held
Procedure and hands control to the `Conductor` runtime, which replays the
pinned step-list tail from the re-establishment boundary (re-drive
setpoints, re-run checks, halt-for-operator on an acquisition), then
auto-completes on a clean tail / aborts on a step failure / leaves
Running on an acquisition halt. Returns a structured
`ConductFromProcedureResult`; replay outcomes are encoded in the result,
not raised.

    from cora.operation.features import conduct_from_procedure

    cmd = conduct_from_procedure.ConductFromProcedure(procedure_id=..., re_establishment_boundary=K)
    handler = conduct_from_procedure.bind(
        deps, conductor=conductor, resume_procedure=..., complete_procedure=..., abort_procedure=...
    )
    result = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.operation.features.conduct_from_procedure import tool
from cora.operation.features.conduct_from_procedure.command import (
    ConductFromProcedure,
    ConductFromProcedureResult,
)
from cora.operation.features.conduct_from_procedure.handler import Handler, bind
from cora.operation.features.conduct_from_procedure.route import (
    ConductFromProcedureRequest,
    ConductFromProcedureResponse,
    router,
)

__all__ = [
    "ConductFromProcedure",
    "ConductFromProcedureRequest",
    "ConductFromProcedureResponse",
    "ConductFromProcedureResult",
    "Handler",
    "bind",
    "router",
    "tool",
]
