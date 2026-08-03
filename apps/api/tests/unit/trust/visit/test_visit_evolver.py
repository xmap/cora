"""Evolver / fold tests: replay determinism + last_status_reason preservation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.trust.aggregates.visit import (
    Visit,
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCheckedIn,
    VisitCheckedOut,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitStatus,
    VisitType,
    VisitVoided,
    evolve,
    fold,
)

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_VID = UUID("01900000-0000-7000-8000-00000000c001")
_PID = UUID("01900000-0000-7000-8000-00000000c002")
_SID = UUID("01900000-0000-7000-8000-00000000c003")


def _registered() -> VisitRegistered:
    return VisitRegistered(
        visit_id=_VID,
        policy_id=_PID,
        surface_id=_SID,
        type=VisitType.USER.value,
        planned_start_at=_NOW,
        planned_end_at=_NOW + timedelta(hours=4),
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_fold_empty_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_genesis_only_yields_planned_state() -> None:
    state = fold([_registered()])
    assert state is not None
    assert state.id == _VID
    assert state.policy_id == _PID
    assert state.surface_id == _SID
    assert state.type == VisitType.USER
    assert state.status == VisitStatus.PLANNED


@pytest.mark.unit
def test_full_lifecycle_walks_through_all_8_states() -> None:
    """Cover Planned -> Arrived -> InProgress <-> OnHold -> Completed.
    +Cancel and +Abort and +Void share the terminal-transition path
    tested separately below."""
    state = fold(
        [
            _registered(),
            VisitArrived(visit_id=_VID, occurred_at=_NOW),
            VisitStarted(visit_id=_VID, occurred_at=_NOW),
            VisitHeld(visit_id=_VID, reason="beam dump", occurred_at=_NOW),
            VisitResumed(visit_id=_VID, occurred_at=_NOW),
            VisitCompleted(visit_id=_VID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == VisitStatus.COMPLETED


@pytest.mark.unit
def test_resume_preserves_last_status_reason_audit_breadcrumb() -> None:
    """Per [[project_visit_aggregate_design]] lock: Resume does NOT clear
    last_status_reason; the prior Hold's reason stays readable for audit."""
    state = fold(
        [
            _registered(),
            VisitArrived(visit_id=_VID, occurred_at=_NOW),
            VisitStarted(visit_id=_VID, occurred_at=_NOW),
            VisitHeld(visit_id=_VID, reason="beam dump", occurred_at=_NOW),
            VisitResumed(visit_id=_VID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == VisitStatus.IN_PROGRESS
    assert state.last_status_reason == "beam dump"


@pytest.mark.parametrize(
    ("terminal_event", "expected_status", "expected_reason"),
    [
        (VisitCompleted(visit_id=_VID, occurred_at=_NOW), VisitStatus.COMPLETED, None),
        (
            VisitCancelled(visit_id=_VID, reason="no-show", occurred_at=_NOW),
            VisitStatus.CANCELLED,
            "no-show",
        ),
        (
            VisitAborted(visit_id=_VID, reason="equipment fault", occurred_at=_NOW),
            VisitStatus.ABORTED,
            "equipment fault",
        ),
        (
            VisitVoided(visit_id=_VID, reason="duplicate", occurred_at=_NOW),
            VisitStatus.VOIDED,
            "duplicate",
        ),
    ],
)
@pytest.mark.unit
def test_all_4_terminators_produce_correct_status_and_reason(
    terminal_event: VisitEvent, expected_status: VisitStatus, expected_reason: str | None
) -> None:
    base: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
    ]
    state = fold([*base, terminal_event])
    assert state is not None
    assert state.status == expected_status
    if expected_reason is None:
        # Completed does not carry a reason; last_status_reason stays None.
        assert state.last_status_reason is None
    else:
        assert state.last_status_reason == expected_reason


@pytest.mark.unit
def test_evolve_replay_is_deterministic() -> None:
    """Same event sequence produces equal Visit instances (frozen dataclass)."""
    events: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
    ]
    first = fold(events)
    second = fold(events)
    assert first == second


@pytest.mark.unit
def test_evolve_step_by_step_matches_fold() -> None:
    events: list[VisitEvent] = [
        _registered(),
        VisitArrived(visit_id=_VID, occurred_at=_NOW),
        VisitStarted(visit_id=_VID, occurred_at=_NOW),
        VisitHeld(visit_id=_VID, reason="r", occurred_at=_NOW),
    ]
    fold_state = fold(events)

    incremental: Visit | None = None
    for e in events:
        incremental = evolve(incremental, e)

    assert incremental == fold_state


_TERMINAL_AT = _NOW + timedelta(hours=3)


def _arrived_history() -> list[VisitEvent]:
    return [_registered(), VisitArrived(visit_id=_VID, occurred_at=_NOW)]


# --- terminal transitions close open presence ------------------------------
#
# A Visit that has completed, been cancelled, aborted or voided has nobody at
# the beamline by implication. The evolver derives that rather than requiring
# per-actor close events, so the fold and `proj_trust_visit_presence` agree
# without the terminal deciders knowing anything about presence.


def _visit_with_two_open_entries(status_event: VisitEvent) -> Visit:
    """Arrived Visit, two actors checked in, then `status_event` applied."""
    a, b = uuid4(), uuid4()
    history: list[VisitEvent] = [
        *_arrived_history(),
        VisitCheckedIn(visit_id=_VID, actor_id=a, mode="physical", occurred_at=_NOW),
        VisitCheckedIn(visit_id=_VID, actor_id=b, mode="remote", occurred_at=_NOW),
        status_event,
    ]
    folded = fold(history)
    assert folded is not None
    return folded


@pytest.mark.parametrize(
    ("status_event", "expected_status"),
    [
        (
            VisitCompleted(visit_id=_VID, occurred_at=_TERMINAL_AT),
            VisitStatus.COMPLETED,
        ),
        (
            VisitCancelled(visit_id=_VID, reason="r", occurred_at=_TERMINAL_AT),
            VisitStatus.CANCELLED,
        ),
        (
            VisitAborted(visit_id=_VID, reason="r", occurred_at=_TERMINAL_AT),
            VisitStatus.ABORTED,
        ),
        (
            VisitVoided(visit_id=_VID, reason="r", occurred_at=_TERMINAL_AT),
            VisitStatus.VOIDED,
        ),
    ],
)
@pytest.mark.unit
def test_terminal_transition_closes_every_open_presence_entry(
    status_event: VisitEvent, expected_status: VisitStatus
) -> None:
    state = _visit_with_two_open_entries(status_event)
    assert state.status is expected_status
    assert len(state.presence_entries) == 2
    assert all(e.check_out_at == _TERMINAL_AT for e in state.presence_entries)


@pytest.mark.unit
def test_terminal_transition_leaves_an_already_closed_entry_at_its_own_time() -> None:
    """A prior check-out keeps its own timestamp; the terminal one does not overwrite it."""
    actor = uuid4()
    earlier = _NOW + timedelta(hours=1)
    history: list[VisitEvent] = [
        *_arrived_history(),
        VisitCheckedIn(visit_id=_VID, actor_id=actor, mode="physical", occurred_at=_NOW),
        VisitCheckedOut(visit_id=_VID, actor_id=actor, occurred_at=earlier),
        VisitCompleted(visit_id=_VID, occurred_at=_TERMINAL_AT),
    ]
    folded = fold(history)
    assert folded is not None
    [entry] = folded.presence_entries
    assert entry.check_out_at == earlier


@pytest.mark.unit
def test_terminal_transition_with_no_presence_changes_nothing() -> None:
    """The no-open-entries path returns the same frozenset, not a rebuilt one."""
    history: list[VisitEvent] = [
        *_arrived_history(),
        VisitCompleted(visit_id=_VID, occurred_at=_TERMINAL_AT),
    ]
    folded = fold(history)
    assert folded is not None
    assert folded.presence_entries == frozenset()
    assert folded.status is VisitStatus.COMPLETED
