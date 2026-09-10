"""The `HoldProcedure` command -- intent dataclass for this slice.

Single-source pause transition: `Running -> Held`. The operator pauses
a halted conduct so it can be re-established and resumed rather than
aborted-and-reseeded (Tier 1 of [[project_resumable_conduct_design]]).

Carries a REQUIRED free-form `reason` (1-500 chars after trim; validated
at the API boundary AND defensively at the decider via the
`ProcedureHoldReason` VO). Unlike `HoldRun` (slim, no reason: a routine
Run pause), pausing a halted conduct is a deliberate, high-information
operator act, so the reason is mandatory (matching `AgentSuspended.reason`).

`decided_by_decision_id` mirrors `HoldRun`: optional Decision-causation
link. The operator-facing route leaves it None; an in-process agent
runtime sets it to link an autonomous hold to its Decision. NO existence
check at the decider per the cross-BC eventual-consistency stance.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.operation.aggregates.procedure import HOLD_CAUSE_OPERATOR


@dataclass(frozen=True)
class HoldProcedure:
    """Pause an actively-running Procedure conduct (Running -> Held)."""

    procedure_id: UUID
    reason: str
    cause: str = HOLD_CAUSE_OPERATOR
    """Which concern is placing or discharging the hold, from `HOLD_CAUSES`.

    Defaults to `operator` so the REST route and the MCP tool, which do NOT
    expose this field, always speak for an operator. A caller able to choose
    its own cause could label a machine-parked conduct as an operator pause;
    the in-process Conductor sets its cause explicitly instead. The claim id
    is NOT a command field: it is derived from (procedure_id, cause), so a
    holder and a releaser agree on it without either storing it."""
    decided_by_decision_id: UUID | None = None
    actuation_kind: str | None = None
    """The raw `ActuationKind` value the Conductor observed in the conduct up
    to this pause. `Conductor.conduct_or_hold` sets it so the pre-hold provenance
    survives the hold->resume boundary (see `ProcedureHeld.actuation_kind`); an
    operator hold issued outside a conduct leaves it None."""
