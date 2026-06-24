"""The `ConductUntilConverged` command, the AUTO-align entry for the loop runtime.

Like `ConductProcedure`, this does not write to an aggregate stream directly.
It hands control to `Conductor.conduct_until_converged`, which drives the full
convergence loop over the Procedure FSM: `start_procedure` -> { `start_iteration`
-> walk one pass -> `end_iteration` } * -> `complete_procedure` (converged) or
`abort_procedure` (the patience cap tripped, or a pass faulted). The handler
returns a `ConductUntilConvergedResult` summarising the run; failures (including
a never-converged cap-abort) are encoded in that result, not raised, so one
client code-path covers every outcome.

`steps` is the per-pass block. For a recipe-driven Procedure the caller passes
an empty sequence and the handler re-expands the pinned recipe (the one-pass
template) before each conduct, mirroring `conduct_procedure`.

The convergence predicate is a conduct-time parameter at slice 6c (pinning it
onto the Procedure aggregate is a deferred follow-on for the 2nd auto-routine):

  - `convergence_capture_name` names the captures slot the per-pass deposit
    fills (a `ComputeStep` with this `capture_name`); the loop reads it after
    each successful pass.
  - `criterion` is the EXISTING `EqualsCriterion | WithinToleranceCriterion`
    union, evaluated by `_criterion_matches` against the captured value.

`max_consecutive_unconverged_iterations` is the optional patience cap the loop
honors (read off the Procedure at register time on the recipe path, passed
through here for the in-process path); None means no patience cap. Even with no
patience cap the loop is bounded by an absolute iteration ceiling
(`Conductor._ABSOLUTE_MAX_ITERATIONS`, defense-in-depth against a never-matching
criterion actuating hardware without bound); hitting it aborts the Procedure
with `AbsoluteIterationCeilingReached`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from cora.operation.conductor import CheckCriterion, ConductorFailure, Step
from cora.operation.ports.measurement import Measurement


@dataclass(frozen=True)
class ConductUntilConverged:
    """Invoke the convergence loop against an existing Procedure + pass block."""

    procedure_id: UUID
    convergence_capture_name: str
    criterion: CheckCriterion
    steps: Sequence[Step] = ()
    max_consecutive_unconverged_iterations: int | None = None


@dataclass(frozen=True)
class ConductUntilConvergedResult:
    """Summary of a `ConductUntilConverged` invocation.

    Mirrors `ConductorResult` shape (procedure_id + completed_count +
    succeeded + optional failure + actuation_kind + measurements) so the
    wire response stays decoupled from the in-process Conductor type.

    `succeeded` is True only when the loop reached the convergence criterion
    and completed the Procedure. A never-converged cap-abort and an in-pass
    fault both surface `succeeded=False` with a `failure` carrying the cause
    (`ConvergenceIterationCapReached` for the patience cap;
    `AbsoluteIterationCeilingReached` for the absolute runaway backstop that
    bites even when no patience cap was set; the step failure verbatim for a
    fault). `measurements` carries the final pass's produced
    `Measurement`s so the caller can record the converged value to a
    Calibration without re-parsing the journal.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
    measurements: tuple[Measurement, ...] = ()
