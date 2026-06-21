"""The `ResumeProcedure` command -- intent dataclass for this slice.

Single-source resume transition: `Held -> Running`. The inverse of
hold_procedure. Carries `re_establishment_boundary`: the index in the
pinned resolved step list from which a resume re-drives setpoints and
re-runs checks (Tier 1 of [[project_resumable_conduct_design]]). It is
NOT a continuity proof; it is the re-establishment boundary the
Conductor's `execute_from` replays from.

`decided_by_decision_id` mirrors `ResumeRun`: optional Decision-causation
link. The operator-facing route leaves it None; an in-process agent
runtime sets it to link an autonomous, safety-gated resume to its
Decision. NO existence check at the decider per the cross-BC
eventual-consistency stance.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeProcedure:
    """Resume a held Procedure conduct (Held -> Running)."""

    procedure_id: UUID
    re_establishment_boundary: int
    decided_by_decision_id: UUID | None = None
