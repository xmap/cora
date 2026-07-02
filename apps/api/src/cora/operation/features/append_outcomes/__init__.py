"""Vertical slice for the `AppendProcedureOutcomes` command.

The steered conduct loop appends one outcome per iteration, recording the
measured values (the y) the brain fit against that pass so a resume can rebuild
the observation history from the record instead of re-measuring. Ships the full
wire surface (route + tool + authz), uniform with every CORA slice.

    from cora.operation.features import append_outcomes

    handler = append_outcomes.bind(deps, outcome_store=store)
    count = await handler(cmd, principal_id=..., correlation_id=...)

Lazy open-on-first-write: the handler emits `ProcedureOutcomeLogbookOpened` to
the Procedure stream the first time an outcome is recorded for a Procedure;
subsequent appends find the logbook attached and skip the open. Mirrors
`append_diagnostics`.
"""

from cora.operation.features.append_outcomes import tool
from cora.operation.features.append_outcomes.command import (
    AppendProcedureOutcomes,
    OutcomeInput,
)
from cora.operation.features.append_outcomes.handler import Handler, bind
from cora.operation.features.append_outcomes.route import router

__all__ = [
    "AppendProcedureOutcomes",
    "Handler",
    "OutcomeInput",
    "bind",
    "router",
    "tool",
]
