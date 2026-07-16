"""Shared fixtures + helpers for Ratification slice tests.

Per-slice tests build state via the canonical fixtures here to avoid
copy-pasted construction across the decider + evolver test files.
"""

from datetime import UTC, datetime
from uuid import UUID

from cora.trust.aggregates.ratification import (
    Ratification,
    RatificationEvent,
    RatificationRequested,
    RatificationStatus,
    fold,
)

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=UTC)
RATIFICATION_ID = UUID("01910000-0000-7000-8000-00000000b001")
TARGET_REF = UUID("01910000-0000-7000-8000-00000000b002")
REQUESTER_ID = UUID("01910000-0000-7000-8000-00000000b003")
OTHER_PRINCIPAL_ID = UUID("01910000-0000-7000-8000-00000000b004")
COMMAND_NAME = "AbortRun"
CONSEQUENCE_CLASS = "first_of_kind"


def make_requested(
    *,
    requested_by: UUID = REQUESTER_ID,
    consequence_class: str = CONSEQUENCE_CLASS,
) -> Ratification:
    """Build a Ratification in the Requested (genesis) state."""
    events: list[RatificationEvent] = [
        RatificationRequested(
            ratification_id=RATIFICATION_ID,
            target_action_id=TARGET_REF,
            command_name=COMMAND_NAME,
            consequence_class=consequence_class,
            requested_by=requested_by,
            occurred_at=NOW,
        )
    ]
    state = fold(events)
    assert state is not None
    assert state.status is RatificationStatus.REQUESTED
    return state
