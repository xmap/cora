"""Pure decider for the `RequestRatification` command.

Genesis transition: (empty) -> Requested. Caller supplies `ratification_id`;
collision raises `RatificationAlreadyExistsError` (state is None means no prior
events; non-None means it already exists).

`requested_by` is threaded in by the handler from the envelope `principal_id`
(not a command field), so the requester recorded on genesis is the actual
issuing principal. Kind-blind: the decider records a bare principal id and never
reads actor kind.
"""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.ratification import (
    CONSEQUENCE_CLASS_MAX_LENGTH,
    InvalidConsequenceClassError,
    Ratification,
    RatificationAlreadyExistsError,
    RatificationRequested,
)
from cora.trust.features.request_ratification.command import RequestRatification


def decide(
    state: Ratification | None,
    command: RequestRatification,
    *,
    requested_by: UUID,
    now: datetime,
) -> list[RatificationRequested]:
    """Decide the events produced by requesting a ratification.

    Invariants:
      - State must be None (caller-supplied id collision guard)
        -> RatificationAlreadyExistsError
      - consequence_class 1-100 chars after trim
        -> InvalidConsequenceClassError
    """
    if state is not None:
        raise RatificationAlreadyExistsError(command.ratification_id)
    trimmed_class = command.consequence_class.strip()
    if not trimmed_class or len(trimmed_class) > CONSEQUENCE_CLASS_MAX_LENGTH:
        raise InvalidConsequenceClassError(command.consequence_class)
    return [
        RatificationRequested(
            ratification_id=command.ratification_id,
            target_action_id=command.target_action_id,
            command_name=command.command_name,
            consequence_class=trimmed_class,
            requested_by=requested_by,
            occurred_at=now,
        )
    ]
