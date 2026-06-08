"""Shared fixtures + helpers for Visit slice tests.

Per-slice tests build state via the canonical fixtures here to avoid
copy-pasted construction across 9 decider test files.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import (
    Visit,
    VisitArrived,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitStarted,
    VisitStatus,
    VisitType,
    fold,
)

NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
VISIT_ID = UUID("01900000-0000-7000-8000-00000000a001")
POLICY_ID = UUID("01900000-0000-7000-8000-00000000a002")
SURFACE_ID = UUID("01900000-0000-7000-8000-00000000a003")
PLANNED_START = NOW
PLANNED_END = NOW + timedelta(hours=8)


def make_registered() -> VisitRegistered:
    """Build a canonical VisitRegistered event for fixture-state construction."""
    return VisitRegistered(
        visit_id=VISIT_ID,
        policy_id=POLICY_ID,
        surface_id=SURFACE_ID,
        type=VisitType.USER.value,
        planned_start_at=PLANNED_START,
        planned_end_at=PLANNED_END,
        occurred_at=NOW,
        parent_id=None,
        external_refs=frozenset({Identifier(scheme="proposal", value="12345")}),
    )


def make_visit(status: VisitStatus) -> Visit:
    """Build a Visit folded from events ending at the requested status.

    Walks the FSM via real event emission so the resulting state
    matches what production would produce (including `last_status_reason`
    population on Held).
    """
    events: list[VisitEvent] = [make_registered()]
    if status == VisitStatus.PLANNED:
        return _must_fold(events)
    events.append(VisitArrived(visit_id=VISIT_ID, occurred_at=NOW))
    if status == VisitStatus.ARRIVED:
        return _must_fold(events)
    events.append(VisitStarted(visit_id=VISIT_ID, occurred_at=NOW))
    if status == VisitStatus.IN_PROGRESS:
        return _must_fold(events)
    if status == VisitStatus.ON_HOLD:
        events.append(VisitHeld(visit_id=VISIT_ID, reason="beam dump", occurred_at=NOW))
        return _must_fold(events)
    # For terminals (Completed / Cancelled / Aborted / Voided) the test
    # caller composes the final event itself; this helper bottoms at
    # non-terminal states only.
    raise ValueError(f"make_visit only handles non-terminal statuses, got: {status.value}")


def _must_fold(events: list[VisitEvent]) -> Visit:
    state = fold(events)
    assert state is not None, "fold returned None for non-empty event sequence"
    return state
