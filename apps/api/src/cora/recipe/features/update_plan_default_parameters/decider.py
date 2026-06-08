"""Pure decider for the `UpdatePlanDefaultParameters` command.

The decider:
  - Raises PlanNotFoundError on empty state
  - Merges the patch into prior default_parameters via RFC 7396 semantics
  - Validates the merged result against the supplied
    `method_parameters_schema` (raises InvalidPlanDefaultParametersError
    on failure; STRICT when method_parameters_schema is None — non-empty
    merged defaults are rejected; mirrors 5g-c's "no Capabilities +
    non-empty settings → reject" anchor; per audit reversal, see
    [[project_run_parameters_design]] §audit-correction)
  - No-ops (returns []) if the merged result equals the current
    default_parameters (matches 5g-c precedent: identical re-submission
    carries no audit value)
  - Otherwise emits PlanDefaultParametersUpdated(plan_id,
    default_parameters, occurred_at) with the FULL post-merge dict in
    the payload (NOT the patch — readers reconstruct current state
    without folding back through prior events)

The handler is responsible for loading the Method stream and
passing its `parameters_schema` into `decide` as the
`method_parameters_schema` argument; the decider stays pure (no I/O).
"""

from datetime import datetime

from cora.recipe.aggregates.plan import (
    Plan,
    PlanDefaultParametersUpdated,
    PlanNotFoundError,
    validate_default_parameters_against_method_schema,
)
from cora.recipe.features.update_plan_default_parameters.command import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters.context import (
    PlanDefaultParametersContext,
)
from cora.shared.json_merge_patch import merge_patch


def decide(
    state: Plan | None,
    command: UpdatePlanDefaultParameters,
    *,
    context: PlanDefaultParametersContext,
    now: datetime,
) -> list[PlanDefaultParametersUpdated]:
    """Decide the events produced by a Plan.default_parameters update.

    Invariants:
      - State must not be None -> PlanNotFoundError
      - Merged default_parameters must validate against the Method's
        parameters_schema (STRICT when schema is None; non-empty
        merged defaults are rejected)
        -> InvalidPlanDefaultParametersError
        (via validate_default_parameters_against_method_schema)
    """
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    merged = merge_patch(state.default_parameters, command.default_parameters_patch)

    validate_default_parameters_against_method_schema(merged, context.method_parameters_schema)

    if merged == state.default_parameters:
        return []

    return [
        PlanDefaultParametersUpdated(
            plan_id=state.id,
            default_parameters=merged,
            occurred_at=now,
        )
    ]
