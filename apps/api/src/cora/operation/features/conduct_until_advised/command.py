"""The `ConductUntilAdvised` command, the steered-loop entry over the wire.

The DECIDE-axis sibling of `ConductUntilConverged`. Like it, this writes to no
aggregate stream directly: it hands control to `Conductor.conduct_until_advised`,
which drives the full measure-then-advise loop over the Procedure FSM
(`start_procedure` -> { `start_iteration` -> walk one pass -> `advise_next` ->
`end_iteration` } * -> `complete_procedure` when the brain advises Stop, or
`abort_procedure` on a pass fault / brain fault / the absolute ceiling). The
handler returns a `ConductUntilAdvisedResult` summarising the run; failures are
encoded in that result, not raised, so one client code-path covers every outcome.

Recipe-driven by construction: the per-pass block carries a `SteeringRef`
setpoint (the loop-seeded axis), which only a Recipe can express (the literal
HTTP step union cannot carry a `SteeringRef`). So there is no `steps` field; the
handler always re-expands the Procedure's pinned recipe, the same path
`conduct_procedure` / `conduct_until_converged` use with an empty step list.

  - `objective` is what "good" means (a `SteeringObjective`: kind + optional
    target measurement name + target value); the brain weighs it.
  - `space` is the feasible `SteeringSpace` (axes + bounds / choices) the brain
    may propose within; each `SteeringAxis.name` must be consumed by a
    `SteeringRef` setpoint in the pinned block.
  - `objective_capture_name` names the captures slot the per-pass deposit fills
    (the objective scalar the brain reads).
  - `decide` selects the in-CORA brain (`DecidePortConfig`: in_memory | grid_walk).
  - `budget` is informational for the brain (not enforced in the loop at this
    slice); None means open-ended.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.conductor import ConductorFailure
from cora.operation.ports.decide_port import (
    SteeringBudget,
    SteeringLlmCall,
    SteeringObjective,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement


@dataclass(frozen=True)
class ConductUntilAdvised:
    """Invoke the steered loop against an existing recipe-driven Procedure."""

    procedure_id: UUID
    objective: SteeringObjective
    space: SteeringSpace
    objective_capture_name: str
    decide: DecidePortConfig
    budget: SteeringBudget | None = None


@dataclass(frozen=True)
class ConductUntilAdvisedResult:
    """Summary of a `ConductUntilAdvised` invocation.

    Mirrors `ConductorResult` shape (procedure_id + completed_count + succeeded
    + optional failure + actuation_kind + measurements) so the wire response
    stays decoupled from the in-process Conductor type.

    `succeeded` is True only when the brain advised Stop and the Procedure
    completed. A pass fault, a brain fault (a folded `Decide*Error`), and the
    absolute iteration ceiling all surface `succeeded=False` with a `failure`
    carrying the cause. `measurements` carries the final pass's produced
    `Measurement`s so the caller can record the steered result to a Calibration
    without re-parsing the journal.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
    measurements: tuple[Measurement, ...] = ()
    llm_calls: tuple[SteeringLlmCall, ...] = ()
    """Usage records for the LLM calls the brain made during this conduct,
    in call order; empty for non-LLM substrates. In-process only (not on
    the wire response): the steer_experiment driver posts these to the
    durable inference ledger against its across-procedure Decision."""
