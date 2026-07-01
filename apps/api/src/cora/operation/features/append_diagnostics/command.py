"""The `AppendProcedureDiagnostics` command, intent dataclass for this slice.

Batch shape from day one (matches `append_activities` / `append_inferences`).
Length-1 batches are the degenerate case; same code path either way. The
conductor's steered loop appends one diagnostic per GP-decided iteration.

Producer-supplied `event_id` (UUIDv7) per entry; the store dedups via the
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`), so a conduct retry that
re-emits the same iteration's diagnostic is a silent no-op.

## Conductor-internal, not a wire slice

Unlike `append_activities`, this slice has NO route/tool: diagnostic rows are
machine-emitted by the conductor during a steered conduct, never posted by an
operator over HTTP/MCP. So the command carries no authz ceremony of its own;
the conduct that drives it is already authorized upstream.

## Lazy open-on-first-write

The handler loads the parent Procedure, checks whether
`procedure.diagnostic_logbook_id` is set, and emits a
`ProcedureDiagnosticLogbookOpened` event lazily on the first diagnostic write.
`start_procedure` stays unchanged; the logbook attaches when the first steered
iteration's diagnostics arrive.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class DiagnosticInput:
    """One diagnostic entry's input payload from the producer (the conductor).

    Mirrors `Diagnostic` but omits the CORA-infra fields (procedure_id /
    logbook_id / correlation_id / causation_id) which the handler populates
    from the command + envelope. `payload` is the deciding brain's opaque map
    of fitted-model summary scalars (lengthscales, noise, acquisition value).
    """

    event_id: UUID
    iteration_index: int
    model_ref: str
    payload: dict[str, Any]
    sampled_at: datetime
    occurred_at: datetime | None = None
    """When the handler appended the entry. Optional from the producer; when
    omitted the handler defaults to `clock.now()`."""


@dataclass(frozen=True)
class AppendProcedureDiagnostics:
    """Append a batch of GP-steering diagnostics to a Procedure's logbook."""

    procedure_id: UUID
    entries: tuple[DiagnosticInput, ...]
