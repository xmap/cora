"""The `AppendProcedureOutcomes` command, intent dataclass for this slice.

Batch shape from day one (matches `append_diagnostics` / `append_activities`).
Length-1 batches are the degenerate case; same code path either way. The
conductor's steered loop appends one outcome per iteration, recording the
measured values (the y) the brain fit against that pass.

Producer-supplied `event_id` (UUIDv7) per entry; the store dedups via the
Postgres PK (`ON CONFLICT (event_id) DO NOTHING`), so a conduct retry that
re-emits the same iteration's outcome is a silent no-op.

## Full wire slice

Like `append_diagnostics`, this slice ships the full wire surface (route +
tool + authz + contract tests). The conductor is the primary caller (one
outcome per steered iteration), but the slice is uniform with every other
CORA slice, so an operator or tool can read/audit the same path and the authz
gate is consistent.

## Lazy open-on-first-write

The handler loads the parent Procedure, checks whether
`procedure.outcome_logbook_id` is set, and emits a
`ProcedureOutcomeLogbookOpened` event lazily on the first outcome write.
`start_procedure` stays unchanged; the logbook attaches when the first steered
pass records its measurements.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class OutcomeInput:
    """One outcome entry's input payload from the producer (the conductor).

    Mirrors `Outcome` but omits the CORA-infra fields (procedure_id /
    logbook_id / correlation_id / causation_id) which the handler populates
    from the command + envelope. `point` is the coordinate map the pass measured
    at (the x); `measurements` is the list of Measurement dicts (value / kind /
    quality / name / units) the pass produced (the y). Both ride the row so a
    resume rebuilds each observation without a join to the iteration event.
    """

    event_id: UUID
    iteration_index: int
    point: dict[str, Any]
    measurements: list[dict[str, Any]]
    succeeded: bool
    actuation_kind: str | None
    sampled_at: datetime
    occurred_at: datetime | None = None
    """When the handler appended the entry. Optional from the producer; when
    omitted the handler defaults to `clock.now()`."""


@dataclass(frozen=True)
class AppendProcedureOutcomes:
    """Append a batch of steered-pass outcomes to a Procedure's logbook."""

    procedure_id: UUID
    entries: tuple[OutcomeInput, ...]
