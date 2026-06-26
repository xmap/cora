"""The `EndProcedureIteration` command -- intent dataclass for this slice.

Single-stream update on a Running Procedure: close the currently-open
convergence-loop iteration. `iteration_index` must match the open
`current_iteration_index` (validated at the decider). `converged`
carries the convergence verdict (True / False / None when no verdict);
`reason` is an optional free-form note bounded at the API boundary.
Slice-dir name drops the aggregate qualifier (`end_iteration`); the
command class carries it (`EndProcedureIteration`). `reason` is
optional; the decider trims and bounds it (1-500 chars) when present.

## Steering provenance (additive, stream-only)

The remaining optional fields carry the per-iteration decision provenance
a steered conduct records (`conduct_until_advised`): `advised_stop` is the
steering verdict (True advised-stop, False continue, None no-verdict, so
`converged` stays None for a steering pass and the convergence streak never
bites), and `reasoning` / `confidence` / `confidence_source` /
`alternatives` / `decision_model_ref` are the advice provenance for the
in-conductor audit ledger, sourced from `advice_to_audit_fields` (so they
carry the SAME names the mapper emits). They are stream-only and default to
absent: a plain convergence or manual `end_iteration` leaves them unset.
They arrive pre-validated from a self-validated `SteeringAdvice` (confidence
in [0,1], rationale bounded), so the decider passes them through rather than
re-validating. `confidence_source` is the typed `DecisionConfidenceSource`,
matching the Decision record so the two audit homes stay type-faithful.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.decision_signals import DecisionConfidenceSource


@dataclass(frozen=True)
class EndProcedureIteration:
    """Close the open convergence-loop iteration on a Running Procedure."""

    procedure_id: UUID
    iteration_index: int
    converged: bool | None
    reason: str | None
    advised_stop: bool | None = None
    reasoning: str | None = None
    confidence: float | None = None
    confidence_source: DecisionConfidenceSource | None = None
    alternatives: tuple[str, ...] = ()
    model_ref: str | None = None
