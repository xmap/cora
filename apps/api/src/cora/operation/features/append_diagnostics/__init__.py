"""Vertical slice for the `AppendProcedureDiagnostics` command.

Conductor-internal: the steered conduct loop appends one GP-steering
diagnostic per learning-brain-decided iteration. No route/tool (unlike
`append_activities`): diagnostics are machine-emitted, never operator-posted.

    from cora.operation.features import append_diagnostics

    handler = append_diagnostics.bind(deps, diagnostic_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits `ProcedureDiagnosticLogbookOpened`
to the Procedure stream the first time diagnostics are recorded for a
Procedure; subsequent appends find the logbook attached and skip the open.
Mirrors `append_activities`.
"""

from cora.operation.features.append_diagnostics import tool
from cora.operation.features.append_diagnostics.command import (
    AppendProcedureDiagnostics,
    DiagnosticInput,
)
from cora.operation.features.append_diagnostics.handler import Handler, bind
from cora.operation.features.append_diagnostics.route import router

__all__ = [
    "AppendProcedureDiagnostics",
    "DiagnosticInput",
    "Handler",
    "bind",
    "router",
    "tool",
]
