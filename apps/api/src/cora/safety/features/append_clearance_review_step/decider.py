"""Pure decider for the `AppendClearanceReviewStep` command.

Append-only-into-tuple, no status change.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` ->
    `ClearanceCannotAppendReviewStepError`
  - `step_index` must equal `len(state.review_steps)` ->
    `InvalidClearanceReviewStepIndexError`
  - `decided_at` must not be in the future relative to `now` (defensive
    guard mirroring `truncate_run` / `truncate_procedure` precedent) ->
    `InvalidClearanceReviewStepDecidedAtError`
  - `decided_at` must be >= the prior step's `decided_at` if a prior
    step exists (chain monotonicity: reviewers decide in order) ->
    `InvalidClearanceReviewStepDecidedAtError`
  - `role` validated 1-50 chars after trim ->
    `InvalidClearanceReviewerRoleError`
  - `notes` validated 0-2000 chars after trim ->
    `InvalidClearanceReviewerNotesError`
  - `decision` membership in `{Approved, Rejected, RequestedChanges}`
    is enforced at the API layer (Pydantic Literal); deciders trust
    typed input
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotAppendReviewStepError,
    ClearanceNotFoundError,
    ClearanceReviewStepAppended,
    ClearanceStatus,
    InvalidClearanceReviewerNotesError,
    InvalidClearanceReviewerRoleError,
    InvalidClearanceReviewStepDecidedAtError,
    InvalidClearanceReviewStepIndexError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.append_clearance_review_step.command import (
    AppendClearanceReviewStep,
)
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.identity import ActorId

_REVIEW_STEP_APPENDABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.UNDER_REVIEW,)


def decide(
    state: Clearance | None,
    command: AppendClearanceReviewStep,
    *,
    now: datetime,
) -> list[ClearanceReviewStepAppended]:
    """Decide the events produced by appending one reviewer step.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be UnderReview
        -> ClearanceCannotAppendReviewStepError
      - step_index must equal len(state.review_steps)
        -> InvalidClearanceReviewStepIndexError
      - decided_at must not be future-dated relative to now
        -> InvalidClearanceReviewStepDecidedAtError
      - decided_at must be >= prior step's decided_at
        (chain monotonicity)
        -> InvalidClearanceReviewStepDecidedAtError
      - Role must be valid
        -> InvalidClearanceReviewerRoleError
      - Notes (when set) must be within length bound
        -> InvalidClearanceReviewerNotesError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _REVIEW_STEP_APPENDABLE_STATUSES:
        raise ClearanceCannotAppendReviewStepError(state.id, state.status)

    expected = len(state.review_steps)
    if command.step_index != expected:
        raise InvalidClearanceReviewStepIndexError(expected=expected, got=command.step_index)

    if command.decided_at > now:
        raise InvalidClearanceReviewStepDecidedAtError(
            command.decided_at,
            reason=f"future-dated relative to now={now.isoformat()}",
        )
    if state.review_steps and command.decided_at < state.review_steps[-1].decided_at:
        raise InvalidClearanceReviewStepDecidedAtError(
            command.decided_at,
            reason=(
                f"chain monotonicity violated: prior step decided_at="
                f"{state.review_steps[-1].decided_at.isoformat()}"
            ),
        )

    role = validate_bounded_text(
        command.role,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        error_class=InvalidClearanceReviewerRoleError,
    )

    notes: str | None
    if command.notes is None:
        notes = None
    else:
        trimmed_notes = command.notes.strip()
        if len(trimmed_notes) > CLEARANCE_REVIEWER_NOTES_MAX_LENGTH:
            raise InvalidClearanceReviewerNotesError(command.notes)
        notes = trimmed_notes if trimmed_notes else None

    return [
        ClearanceReviewStepAppended(
            clearance_id=state.id,
            step_index=command.step_index,
            role=role,
            decided_by=ActorId(command.actor_id),
            decision=command.decision,
            decided_at=command.decided_at,
            notes=notes,
            occurred_at=now,
        )
    ]
