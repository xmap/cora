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

from cora.operation.aggregates.procedure import HOLD_CAUSE_OPERATOR


@dataclass(frozen=True)
class ResumeProcedure:
    """Resume a held Procedure conduct (Held -> Running)."""

    procedure_id: UUID
    re_establishment_boundary: int
    cause: str = HOLD_CAUSE_OPERATOR
    """Which concern is placing or discharging the hold, from `HOLD_CAUSES`.

    Defaults to `operator` so the REST route and the MCP tool, which do NOT
    expose this field, always speak for an operator. A caller able to choose
    its own cause could label a machine-parked conduct as an operator pause;
    the in-process Conductor sets its cause explicitly instead. The claim id
    is NOT a command field: it is derived from (procedure_id, cause), so a
    holder and a releaser agree on it without either storing it."""
    decided_by_decision_id: UUID | None = None
