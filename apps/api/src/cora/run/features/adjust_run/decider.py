"""Pure decider for the `AdjustRun` command.

Mid-flight parameter steering: an in-progress Run keeps its identity
+ Subject + Plan + Method + Asset binding + Campaign membership +
FSM continuity while recording a parameter mutation as an additive
event on the Run's stream. Source-state guard `{Running, Held}`
(Idle/Starting use `override_parameters` at start_run; terminal
states are by definition frozen).

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most fundamental
issues surface first:

  1. State must not be None -> `RunNotFoundError` (reused from Run BC).
  2. State.status must be in `_ADJUSTABLE_STATUSES` (RUNNING | HELD)
     -> `RunCannotAdjustError(run_id, current_status)`.
  3. `parameters_patch` must be non-empty (len > 0)
     -> `InvalidRunAdjustPatchError("must contain at least one change")`.
  4. `reason` length 1-500 chars after trim
     -> `InvalidRunAdjustReasonError`.
  5. Compute `merged = merge_patch(state.effective_parameters, patch)`;
     when `context.method_parameters_schema is not None`, validate
     `merged` against the schema (RELAXED posture per the 5g-c
     STRICT anchor at start_run vs the steering posture at adjust;
     schemaless Methods skip validation here). Delegates to
     `parameters_validation.validate_adjusted_parameters_against_method_schema`.
     -> `InvalidRunAdjustSchemaError(detail)` on violation.
  6. Emit `RunAdjusted(run_id, parameters_patch, effective_parameters=merged,
     reason=trimmed, decided_by_decision_id, occurred_at=now)`.

The merged effective set is emitted on the payload (alongside the
patch) so projections / read endpoints don't need to fold prior
RunAdjusted events to surface the current value. Mirrors
`RunStarted.effective_parameters` snapshot precedent.

`decided_by_decision_id` flows through to the event payload
verbatim. NOT verified at decider (eventual-consistency stance per
Trust.Conduit / Asset parent / Procedure target / Campaign
lead_actor / Run.subject_id precedent).

## Schema validation posture

See `cora.run.aggregates.run.parameters_validation` for the STRICT
(start_run) vs RELAXED (adjust_run) sibling adapters and
`docs/reference/patterns.md` "Schema validation posture" for the
cross-BC convention. Adjust-time uses RELAXED: once an operator
started a Run on a schemaless Method, they carry full responsibility
for steering it; we don't second-guess at adjust time.
"""

from datetime import datetime

from cora.run.aggregates.run import (
    InvalidRunAdjustPatchError,
    InvalidRunAdjustReasonError,
    Run,
    RunAdjusted,
    RunCannotAdjustError,
    RunNotFoundError,
    RunStatus,
    validate_adjusted_parameters_against_method_schema,
)
from cora.run.features.adjust_run.command import AdjustRun
from cora.run.features.adjust_run.context import RunAdjustContext
from cora.shared.identity import ActorId
from cora.shared.json_merge_patch import merge_patch
from cora.shared.text_bounds import REASON_MAX_LENGTH

_ADJUSTABLE_STATUSES: tuple[RunStatus, ...] = (RunStatus.RUNNING, RunStatus.HELD)


def _validate_reason(value: str) -> str:
    """Trim + bound-check the operator-supplied reason.

    Mirrors the `validate_bounded_text` shape but raises the
    adjust-specific error class for unambiguous API responses.
    """
    trimmed = value.strip()
    if not trimmed or len(trimmed) > REASON_MAX_LENGTH:
        raise InvalidRunAdjustReasonError(value)
    return trimmed


def decide(
    state: Run | None,
    command: AdjustRun,
    *,
    context: RunAdjustContext,
    adjusted_by: ActorId,
    now: datetime,
) -> list[RunAdjusted]:
    """Decide the events produced by adjusting an in-progress Run.

    Invariants:
      - State must not be None -> RunNotFoundError
      - Current status must be Running or Held -> RunCannotAdjustError
      - parameters_patch must be non-empty
        -> InvalidRunAdjustPatchError
      - Reason must be 1-REASON_MAX_LENGTH chars after
        trim -> InvalidRunAdjustReasonError
      - When Method has a parameters_schema, merged effective
        parameters must validate (RELAXED)
        -> InvalidRunAdjustSchemaError
        (via validate_adjusted_parameters_against_method_schema)

    `state` is the source-state Run (None means the Run has no stream;
    raises `RunNotFoundError`). `context.method_parameters_schema` is
    the Method's optional schema (None means schemaless Method;
    validation skipped per the RELAXED adjust-time posture).
    `adjusted_by` is the ActorId of the principal issuing the adjust;
    threaded onto the emitted `RunAdjusted.adjusted_by` per the fold-
    symmetry pair rule ([[project_fold_symmetry_design]]). `now` is
    the wall clock from the handler (injected per non-determinism
    principle).
    """
    if state is None:
        raise RunNotFoundError(command.run_id)

    if state.status not in _ADJUSTABLE_STATUSES:
        raise RunCannotAdjustError(state.id, current_status=state.status)

    if not command.parameters_patch:
        raise InvalidRunAdjustPatchError("must contain at least one change")

    trimmed_reason = _validate_reason(command.reason)

    merged = merge_patch(state.effective_parameters, command.parameters_patch)
    validate_adjusted_parameters_against_method_schema(merged, context.method_parameters_schema)

    return [
        RunAdjusted(
            run_id=state.id,
            parameters_patch=command.parameters_patch,
            effective_parameters=merged,
            reason=trimmed_reason,
            adjusted_by=adjusted_by,
            decided_by_decision_id=command.decided_by_decision_id,
            occurred_at=now,
        )
    ]
