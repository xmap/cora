"""Property-based tests for `close_visit_presence.decide` (Trust BC, Visit).

Complements the example-based `visit/test_close_visit_presence_decider.py`.
The decider closes ANOTHER actor's entry, so its shape is:

    (state, command, now) -> list[VisitCheckedOut]

Load-bearing properties, all chosen for what distinguishes this slice from
`check_out_visit` rather than what it shares:

  - Targets the NAMED actor, never the caller. The command carries the
    actor, and the emitted event must key on `command.actor_id` whatever
    else is present on the Visit.
  - Bystander isolation: closing one actor's entry never emits an event
    naming a different actor, even when several are open at once. This is
    the property that would catch a decider closing "the first open entry"
    instead of the named one.
  - Existence guard: a None state always raises `VisitNotFoundError`.
  - Absence partition: an actor with no open entry always raises
    `VisitActorNotCheckedInError` carrying the state's id and the command's
    actor_id, whether the set is empty or holds only other actors.
  - Lifecycle independence across non-terminal statuses: no status guard,
    an open entry is the only precondition. Terminal statuses are excluded
    because the evolver has already closed every entry by then, so that
    combination is unreachable rather than merely untested.
  - Pure: same inputs return equal results (no clock leakage).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitActorNotCheckedInError,
    VisitNotFoundError,
    VisitPresenceClosed,
    VisitStatus,
)
from cora.trust.features.close_visit_presence import CloseVisitPresence
from cora.trust.features.close_visit_presence.decider import decide
from tests._strategies import aware_datetimes
from tests.unit.trust.visit._fixtures import VISIT_ID, make_visit

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

# Terminal statuses are absent deliberately, and `make_visit` refuses to build
# them. A terminal Visit has already had every open entry closed by the
# evolver's `_closed_at`, so "terminal Visit WITH an open entry" is a state the
# fold cannot produce; asserting over it would test a fiction.
_NON_TERMINAL_STATUSES = (
    VisitStatus.PLANNED,
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def _state_with_open_entries(
    *,
    actor_ids: frozenset[UUID],
    check_in_at: datetime,
    status: VisitStatus = VisitStatus.IN_PROGRESS,
) -> Visit:
    base = make_visit(status)
    return replace(
        base,
        presence_entries=frozenset(
            PresenceEntry(
                actor_id=a,
                mode=PresenceMode.PHYSICAL,
                check_in_at=check_in_at,
                check_out_at=None,
            )
            for a in actor_ids
        ),
    )


@pytest.mark.unit
@given(target=st.uuids(), bystanders=st.frozensets(st.uuids(), max_size=4), now=aware_datetimes())
def test_close_presence_always_names_the_commanded_actor(
    target: UUID, bystanders: frozenset[UUID], now: datetime
) -> None:
    assume(target not in bystanders)
    state = _state_with_open_entries(actor_ids=frozenset({target}) | bystanders, check_in_at=now)
    events = decide(
        state=state,
        command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=target),
        now=now,
    )
    [e] = events
    assert isinstance(e, VisitPresenceClosed)
    assert e.actor_id == target
    assert e.visit_id == state.id
    assert e.occurred_at == now


@pytest.mark.unit
@given(
    target=st.uuids(),
    bystanders=st.frozensets(st.uuids(), min_size=1, max_size=4),
    now=aware_datetimes(),
)
def test_close_presence_never_touches_a_bystander(
    target: UUID, bystanders: frozenset[UUID], now: datetime
) -> None:
    """Catches a decider that closes the first open entry rather than the named one."""
    assume(target not in bystanders)
    state = _state_with_open_entries(actor_ids=frozenset({target}) | bystanders, check_in_at=now)
    events = decide(
        state=state,
        command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=target),
        now=now,
    )
    assert all(e.actor_id not in bystanders for e in events)


@pytest.mark.unit
@given(actor_id=st.uuids(), now=aware_datetimes())
def test_close_presence_on_absent_state_always_raises_not_found(
    actor_id: UUID, now: datetime
) -> None:
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=actor_id),
            now=now,
        )


@pytest.mark.unit
@given(target=st.uuids(), others=st.frozensets(st.uuids(), max_size=4), now=aware_datetimes())
def test_close_presence_raises_when_target_has_no_open_entry(
    target: UUID, others: frozenset[UUID], now: datetime
) -> None:
    assume(target not in others)
    state = _state_with_open_entries(actor_ids=others, check_in_at=now)
    with pytest.raises(VisitActorNotCheckedInError) as exc:
        decide(
            state=state,
            command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=target),
            now=now,
        )
    assert exc.value.visit_id == state.id
    assert exc.value.actor_id == target


@pytest.mark.unit
@given(actor_id=st.uuids(), status=st.sampled_from(_NON_TERMINAL_STATUSES), now=aware_datetimes())
def test_close_presence_is_lifecycle_independent(
    actor_id: UUID, status: VisitStatus, now: datetime
) -> None:
    """No status guard: an open entry is the only precondition."""
    state = _state_with_open_entries(
        actor_ids=frozenset({actor_id}), check_in_at=now, status=status
    )
    events = decide(
        state=state,
        command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=actor_id),
        now=now,
    )
    assert len(events) == 1


@pytest.mark.unit
@given(actor_id=st.uuids(), now=aware_datetimes())
def test_close_presence_is_pure_same_input_same_output(actor_id: UUID, now: datetime) -> None:
    state = _state_with_open_entries(actor_ids=frozenset({actor_id}), check_in_at=now)
    command = CloseVisitPresence(visit_id=VISIT_ID, actor_id=actor_id)
    assert decide(state=state, command=command, now=now) == decide(
        state=state, command=command, now=now
    )
