"""The `ConductUntilAdvisedFrom` command + result, the steered-RESUME entry.

The DECIDE-axis twin of `ReconductProcedure`: where that resumes a flat pinned
step list, this resumes an iterating GP-steered loop. It re-seeds the brain from
the recorded closed passes and consults it only at the open frontier, so the
already-measured passes are neither re-driven nor re-measured (strategy A per
[[project_resumable_conduct_design]]: recorded results replayed, side effects
not re-run).

Carries the same steering config as `ConductUntilAdvised` (objective, space,
objective_capture_name, decide, budget): the resumed frontier passes evaluate
against the rebuilt brain, so the request re-supplies what good means + the
search space + the brain selection. The re-establishment boundary is NOT a
request field: it is DERIVED from the count of recorded closed passes, so the
operator cannot mis-declare it.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.operation.adapters.decide_port_config import DecidePortConfig
from cora.operation.conductor import ConductorFailure
from cora.operation.ports.decide_port import (
    SteeringBudget,
    SteeringObjective,
    SteeringSpace,
)
from cora.operation.ports.measurement import Measurement


@dataclass(frozen=True)
class ConductUntilAdvisedFrom:
    """Resume a Held recipe-driven steered Procedure at the open frontier."""

    procedure_id: UUID
    objective: SteeringObjective
    space: SteeringSpace
    objective_capture_name: str
    decide: DecidePortConfig
    budget: SteeringBudget | None = None


@dataclass(frozen=True)
class ConductUntilAdvisedFromResult:
    """Summary of a `ConductUntilAdvisedFrom` invocation.

    Mirrors `ConductUntilAdvisedResult` plus `re_establishment_boundary` (the
    derived count of closed passes the resume re-seeded from, echoed for the
    operator's audit). `succeeded` is True only when the resumed loop reached a
    brain-advised Stop and the Procedure completed; a pass fault, a brain fault,
    or the absolute ceiling surface `succeeded=False` with `failure` carrying
    the cause. `measurements` carries the final pass's produced `Measurement`s.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    re_establishment_boundary: int
    failure: ConductorFailure | None = None
    actuation_kind: str | None = None
    measurements: tuple[Measurement, ...] = ()
