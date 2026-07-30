"""The `ResumeRun` command — intent dataclass for this slice.

Resume transition: `Held -> Running`, discharging ONE hold claim and
only when it is the last one active. The inverse of hold_run. No reason
field — resume is just permission to proceed — but the command carries
`cause` so the decider knows WHOSE claim is being discharged.

When other concerns still hold the Run the decider emits
`HoldClaimReleased` instead and the Run stays Held; when the caller's own
claim is not active at all it raises rather than resuming past a hold it
did not place.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.run.aggregates.run import HOLD_CAUSE_OPERATOR


@dataclass(frozen=True)
class ResumeRun:
    """Resume a held Run (Held → Running).

    `decided_by_decision_id` (mirrors HoldRun): optional Decision BC
    reference to the record that justified this resume. The operator-
    facing route leaves it None (routine resumes need no justification);
    the in-process RunSupervisor sets it to link an autonomous, safety-
    gated resume to its Decision. NO existence check at the decider per
    the cross-BC eventual-consistency stance.

    `cause` names whose claim this resume discharges, and must match the
    `cause` the hold was placed under. Defaults to `operator`, which is
    what the operator route and tool mean.
    """

    run_id: UUID
    decided_by_decision_id: UUID | None = None
    cause: str = HOLD_CAUSE_OPERATOR
