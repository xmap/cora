"""The `ResumeRun` command — intent dataclass for this slice.

Single-source resume transition: `Held -> Running`. No body at the API
layer. The inverse of hold_run. No reason field — resume is just
permission to proceed.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeRun:
    """Resume a held Run (Held → Running).

    `decided_by_decision_id` (mirrors HoldRun): optional Decision BC
    reference to the record that justified this resume. The operator-
    facing route leaves it None (routine resumes need no justification);
    the in-process RunSupervisor sets it to link an autonomous, safety-
    gated resume to its Decision. NO existence check at the decider per
    the cross-BC eventual-consistency stance.
    """

    run_id: UUID
    decided_by_decision_id: UUID | None = None
