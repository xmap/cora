"""Pure decider for the `RateDecision` command.

Pure function: given the current Decision state (must exist) and a
`RateDecision` command, returns a single `DecisionRated` event. No
I/O, no awaits, no side effects.

Multiple ratings per (decision, actor) pair are ALLOWED. The decider
does NOT raise on a duplicate rating from the same actor: the
evolver folds latest-per-actor wins, and the audit trail keeps all
events. Operators can change their mind; the projection reflects
the latest opinion.

`now` and `rated_by` are injected by the application
handler from the Clock port and request envelope's `principal_id`.

## Validation

  - State must not be None (Decision must exist) -> `DecisionNotFoundError`
  - `comment` (when not None) wrapped via
    `validate_decision_rating_comment(...)`; empty / whitespace-only
    / over-cap raise `InvalidDecisionRatingCommentError`

The `rating` enum value is already type-narrow at the boundary
(Pydantic Literal on the route; typed at the MCP tool argument); no
explicit validation needed here.
"""

from datetime import datetime

from cora.decision.aggregates.decision import (
    Decision,
    DecisionNotFoundError,
    DecisionRated,
    validate_decision_rating_comment,
)
from cora.decision.features.rate_decision.command import RateDecision
from cora.shared.identity import ActorId


def decide(
    state: Decision | None,
    command: RateDecision,
    *,
    now: datetime,
    rated_by: ActorId,
) -> list[DecisionRated]:
    """Decide the events produced by rating an existing Decision.

    Invariants:
      - State must not be None (Decision must exist)
        -> DecisionNotFoundError
      - Comment (when not None) must be non-empty, non-whitespace-only,
        and within cap -> InvalidDecisionRatingCommentError
        (via validate_decision_rating_comment)

    Captures `state.confidence` into the event's
    `confidence_at_rating` field (gate-review cross-BC P2-4
    payload-borne denorm; avoids the cross-projection apply-time
    race the earlier projection-side denorm pattern would have
    suffered under rebuild). `rated_at` and `occurred_at` both
    carry `now` at write time and only diverge on replay (envelope
    vs domain timestamp distinction per
    [[project-naming-conventions]]).
    """
    if state is None:
        raise DecisionNotFoundError(command.decision_id)

    comment = validate_decision_rating_comment(command.comment)

    return [
        DecisionRated(
            decision_id=state.id,
            rating=command.rating,
            comment=comment,
            rated_by=rated_by,
            rated_at=now,
            occurred_at=now,
            confidence_at_rating=state.confidence,
        )
    ]
