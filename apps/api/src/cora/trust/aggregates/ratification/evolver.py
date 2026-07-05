"""Evolver: replay events to reconstruct Ratification state.

Mirror of the Visit / Policy evolvers for Ratification's 3-state FSM. The
terminal `assert_never` case forces pyright (and the runtime) to error if a new
event type is added to `RatificationEvent` without a matching match arm.

`RatificationRequested` is genesis and ignores prior state. `RatificationGranted`
/ `RatificationDenied` update the existing state's `status` (and `last_reason` on
deny), preserving everything else.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.trust.aggregates.ratification.events import (
    RatificationDenied,
    RatificationEvent,
    RatificationGranted,
    RatificationRequested,
)
from cora.trust.aggregates.ratification.state import Ratification, RatificationStatus


def evolve(state: Ratification | None, event: RatificationEvent) -> Ratification:
    """Apply one event to the current state."""
    match event:
        case RatificationRequested(
            ratification_id=ratification_id,
            target_action_id=target_action_id,
            command_name=command_name,
            consequence_class=consequence_class,
            requested_by=requested_by,
        ):
            _ = state  # RatificationRequested is genesis; prior state ignored
            return Ratification(
                id=ratification_id,
                target_action_id=target_action_id,
                command_name=command_name,
                consequence_class=consequence_class,
                requested_by=requested_by,
                status=RatificationStatus.REQUESTED,
                last_reason=None,
            )
        case RatificationGranted():
            assert state is not None, "RatificationGranted requires prior state"
            return replace(state, status=RatificationStatus.GRANTED)
        case RatificationDenied(reason=reason):
            assert state is not None, "RatificationDenied requires prior state"
            return replace(state, status=RatificationStatus.DENIED, last_reason=reason)
        case _:  # pragma: no cover - exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RatificationEvent]) -> Ratification | None:
    """Replay a stream of events from the empty initial state."""
    state: Ratification | None = None
    for event in events:
        state = evolve(state, event)
    return state


__all__ = ["evolve", "fold"]
