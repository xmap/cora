"""The `ReconductProcedure` command + result -- intent dataclass for this slice.

Resume-and-replay orchestration: resume a `Held` Procedure and replay its
PINNED step-list tail from the re-establishment boundary (Tier 1 of
[[project_resumable_conduct_design]]). Mirrors `ConductProcedure` (the
conduct orchestration) but for the resume path; carries the
`re_establishment_boundary` (single-sourced -- it rides into both
`ProcedureResumed` and `Conductor.execute_from`).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.operation.conductor import ConductorFailure


@dataclass(frozen=True)
class ReconductProcedure:
    """Resume a held Procedure and replay its pinned step-list tail."""

    procedure_id: UUID
    re_establishment_boundary: int


@dataclass(frozen=True)
class ReconductProcedureResult:
    """Outcome of a reconduct (resume + replay).

    `succeeded` is the canonical pass/fail bit (the replay's outcome).
    `acquisition_halt` is True iff replay stopped at an acquisition that
    needs an operator decision (redo-fresh vs reseed): in that case the
    Procedure is LEFT Running (no complete, no abort) and `failure` carries
    the halt. On a clean replay the Procedure is auto-completed; on a
    genuine step failure it is aborted. `completed_count` is the number of
    re-driven / re-run tail steps that succeeded; `actuation_kind` is the
    Conductor's observed kind over the replay (None when nothing
    instrumented was actuated).
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    acquisition_halt: bool = False
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
