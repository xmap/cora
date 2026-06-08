"""Pure decider for the `dismiss_event_in_reaction` slice.

Inputs are gathered by the handler (current bookmark cursor, target
event cursor + type) and passed in via `DismissalContext` so the
decider stays pure. Output is the single `DecisionRegistered` event
the handler then appends to the Decision stream atomically with the
bookmark advance.

The slice has no folded aggregate state (the bookmark + event row
are loaded by the handler and passed in via `context`), so `state`
is always None at the canonical decider signature.

Invariants:

  - Reason must be non-empty after strip with length <= 500 chars
    -> InvalidDismissalReasonError.
  - Target event must be STRICTLY AFTER the current bookmark in
    lexicographic `(transaction_id, position)` order. Equal-or-
    behind would be a rewind (or a no-op) and the worker would
    redeliver the same event -> EventAlreadyDismissedError.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.agent.errors import (
    EventAlreadyDismissedError,
    InvalidDismissalReasonError,
)
from cora.agent.features.dismiss_event_in_reaction.command import (
    DismissEventInReaction,
)
from cora.decision.aggregates.decision.events import DecisionRegistered
from cora.decision.aggregates.decision.state import (
    DECISION_CONTEXT_REACTION_DISMISSAL,
)
from cora.shared.identity import ActorId

_REASON_MIN_LENGTH = 1
_REASON_MAX_LENGTH = 500
_DISMISSAL_CHOICE = "EventDismissed"


@dataclass(frozen=True)
class DismissalContext:
    """Pure inputs the handler resolves before calling `decide`.

    Carries everything the decider needs to validate the dismissal
    and stamp the audit event. The handler owns the SQL queries that
    populate this; the decider owns the rules that make the dismissal
    legal.
    """

    bookmark_transaction_id: int
    bookmark_position: int
    event_transaction_id: int
    event_position: int
    event_type: str
    event_recorded_at: datetime


def decide(
    state: None,
    command: DismissEventInReaction,
    *,
    context: DismissalContext,
    new_decision_id: UUID,
    principal_id: UUID,
    now: datetime,
) -> DecisionRegistered:
    """Validate the dismissal, return the audit `DecisionRegistered`.

    `state` is always None (no folded aggregate; the bookmark + event
    row are loaded directly by the handler and passed via `context`).
    Kept as the first positional arg to satisfy the canonical decider
    signature (`decide(state, command, *, ...)`).

    The handler also advances `projection_bookmarks` to
    `(event_transaction_id, event_position)` atomically with appending
    this event; the decider only emits the audit record because the
    bookmark advance is an infrastructure side effect, not a domain
    event.
    """
    _ = state  # canonical signature; this slice has no folded state
    trimmed_reason = command.reason.strip()
    if not trimmed_reason or len(trimmed_reason) < _REASON_MIN_LENGTH:
        raise InvalidDismissalReasonError(
            f"reason must be non-empty after strip; got {command.reason!r}"
        )
    if len(trimmed_reason) > _REASON_MAX_LENGTH:
        raise InvalidDismissalReasonError(
            f"reason must be at most {_REASON_MAX_LENGTH} chars after strip; "
            f"got {len(trimmed_reason)}"
        )

    bookmark_cursor = (context.bookmark_transaction_id, context.bookmark_position)
    event_cursor = (context.event_transaction_id, context.event_position)
    if event_cursor <= bookmark_cursor:
        raise EventAlreadyDismissedError(
            subscriber_name=command.subscriber_name,
            event_id=command.event_id,
            bookmark_transaction_id=context.bookmark_transaction_id,
            bookmark_position=context.bookmark_position,
            event_transaction_id=context.event_transaction_id,
            event_position=context.event_position,
        )

    bluf = (
        f"Operator dismissed event {command.event_id} on subscriber "
        f"{command.subscriber_name!r}: {trimmed_reason}"
    )

    inputs: dict[str, object] = {
        "subscriber_name": command.subscriber_name,
        "event_id": str(command.event_id),
        "event_type": context.event_type,
        "event_transaction_id": str(context.event_transaction_id),
        "event_position": str(context.event_position),
        "previous_bookmark_transaction_id": str(context.bookmark_transaction_id),
        "previous_bookmark_position": str(context.bookmark_position),
    }

    return DecisionRegistered(
        decision_id=new_decision_id,
        decided_by=ActorId(principal_id),
        context=DECISION_CONTEXT_REACTION_DISMISSAL,
        choice=_DISMISSAL_CHOICE,
        parent_id=None,
        override_kind=None,
        rule=None,
        reasoning=bluf,
        confidence=None,
        confidence_source=None,
        alternatives=(),
        inputs=inputs,
        reasoning_signature=None,
        occurred_at=now,
    )
