"""Operation-BC-local read port over a Procedure's recorded steered outcomes.

The read half that steered RESUME needs and the write side does not provide.
The outcome entries written by `append_outcomes` land in
`entries_operation_procedure_outcomes` via a write-only `OutcomeStore`, and the
procedure aggregate stream carries only the one-time
`ProcedureOutcomeLogbookOpened` marker, not the per-pass measured values. So
"what did each closed steered pass measure" has no existing read path.

## Why it exists: re-seed the brain from the record

`conduct_until_advised_from` resumes a Held GP-steered Procedure by re-conditioning
the brain on the closed passes' recorded observations instead of re-measuring
hardware (strategy A: recorded results replayed, side effects not re-run). The
measured y of each closed pass lives ONLY in the outcome side table; the advised
coordinate x lives on the `ProcedureIterationEnded` event. The resume handler
reads both and pairs them via `iteration_index` into the
`_steering_resume.RecordedPass` list the reconstruction consumes. This port is
the y-side read.

## BC-local, not promoted to infrastructure/ports

The sole consumer is the `conduct_until_advised_from` handler, an Operation-BC
slice, and the data-owning sibling `OutcomeStore` is itself BC-internal. So this
read counterpart lives beside the BC, mirroring the `ProcedureActivityLookup`
single-consumer precedent. Promote to `infrastructure/ports/` only on a real
second cross-BC consumer (rule-of-three).
"""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class RecordedOutcome:
    """One closed steered pass's recorded observation (self-describing x + y).

    Mirrors the `Outcome` entry's decision-relevant fields: `iteration_index` is
    the ascending ORDER key (gaps from abandoned passes are tolerated by a
    sort-then-map reconstruction); `point` is the coordinate the pass measured
    at (the x); `measurements` is the recorded Measurement-dict list observed
    there (the y); `succeeded` mirrors the observation success flag (a failed
    acquisition is a real datum); `actuation_kind` threads the Physical /
    Simulated / Hybrid provenance so a resumed fit distrusts a simulated
    outcome. Read-model shape, decoupled from the write-side `Outcome` dataclass
    (no event_id / logbook_id / timestamps: the reconstruction needs none).
    Because the point rides the row, reconstruction needs NO join to the
    iteration event's advised_next_point.
    """

    iteration_index: int
    point: dict[str, Any]
    measurements: list[dict[str, Any]]
    succeeded: bool
    actuation_kind: str | None


class ProcedureOutcomeLookup(Protocol):
    """Read a Procedure's recorded steered outcomes for resume reconstruction.

    One method: every recorded outcome for a procedure, ascending by
    `iteration_index`. Production adapter: `PostgresProcedureOutcomeLookup`
    (operation/adapters/), backed by querying the existing
    `entries_operation_procedure_outcomes` table.
    """

    async def read_procedure_outcomes(self, *, procedure_id: UUID) -> tuple[RecordedOutcome, ...]:
        """Every recorded outcome for `procedure_id`, ascending by iteration_index.

        Returns an empty tuple when the procedure recorded no outcomes (never a
        steered conduct, or interrupted before its first pass closed)."""
        ...


__all__ = [
    "ProcedureOutcomeLookup",
    "RecordedOutcome",
]
