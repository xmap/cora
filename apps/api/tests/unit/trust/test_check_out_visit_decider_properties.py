"""Property-based tests for `check_out_visit.decide` (Trust BC, Visit).

Complements the example-based `visit/test_check_out_visit_decider.py` with
universal claims across generated inputs. This is a bespoke actor
check-out decider returning `list[VisitCheckedOut]`:

    (state, command, now) -> list[VisitCheckedOut]

Load-bearing properties:

  - Existence guard: a None state always raises `VisitNotFoundError`,
    regardless of the command's ids or the clock.
  - Source-state partition: an actor with no open presence entry (empty
    set, or only a closed entry) always raises
    `VisitActorNotCheckedInError` carrying the state's id and the
    command's actor_id.
  - Injected-field threading: a checked-in actor emits exactly one
    `VisitCheckedOut` keyed on state.id, the command's actor_id, and
    occurred_at=now, lifecycle-independent across non-terminal statuses.
  - Pure: same inputs return equal results (no clock leakage).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    Visit,
    VisitActorNotCheckedInError,
    VisitCheckedOut,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.check_out_visit import CheckOutVisit
from cora.trust.features.check_out_visit.decider import decide
from tests._strategies import aware_datetimes
from tests.unit.trust.visit._fixtures import VISIT_ID, make_visit

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NON_TERMINAL_SOURCES = (
    VisitStatus.PLANNED,
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def _state_with_open_entry(
    *,
    actor_id: UUID,
    check_in_at: datetime,
    status: VisitStatus = VisitStatus.IN_PROGRESS,
) -> Visit:
    base = make_visit(status)
    return replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=check_in_at,
                    check_out_at=None,
                )
            }
        ),
    )


def _state_with_closed_entry(
    *,
    actor_id: UUID,
    check_in_at: datetime,
    check_out_at: datetime,
    status: VisitStatus = VisitStatus.IN_PROGRESS,
) -> Visit:
    base = make_visit(status)
    return replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=check_in_at,
                    check_out_at=check_out_at,
                )
            }
        ),
    )


@pytest.mark.unit
@given(visit_id=st.uuids(), actor_id=st.uuids(), now=aware_datetimes())
def test_check_out_none_state_always_raises_not_found(
    visit_id: UUID,
    actor_id: UUID,
    now: datetime,
) -> None:
    """A None state raises VisitNotFoundError for any command ids and clock."""
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=CheckOutVisit(visit_id=visit_id, actor_id=actor_id),
            now=now,
        )


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    source=st.sampled_from(_NON_TERMINAL_SOURCES),
    now=aware_datetimes(),
)
def test_check_out_actor_with_no_entry_always_raises_not_checked_in(
    actor_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """An actor with no presence entry raises VisitActorNotCheckedInError."""
    state = make_visit(source)
    with pytest.raises(VisitActorNotCheckedInError) as exc:
        decide(
            state=state,
            command=CheckOutVisit(visit_id=VISIT_ID, actor_id=actor_id),
            now=now,
        )
    assert exc.value.visit_id == state.id
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    source=st.sampled_from(_NON_TERMINAL_SOURCES),
    now=aware_datetimes(),
)
def test_check_out_already_closed_actor_always_raises_not_checked_in(
    actor_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """An actor whose only entry is already closed has no open presence."""
    state = _state_with_closed_entry(
        actor_id=actor_id,
        check_in_at=now - timedelta(hours=4),
        check_out_at=now - timedelta(hours=2),
        status=source,
    )
    with pytest.raises(VisitActorNotCheckedInError) as exc:
        decide(
            state=state,
            command=CheckOutVisit(visit_id=VISIT_ID, actor_id=actor_id),
            now=now,
        )
    assert exc.value.visit_id == state.id
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    source=st.sampled_from(_NON_TERMINAL_SOURCES),
    now=aware_datetimes(),
)
def test_check_out_open_entry_emits_checked_out_threading_id_actor_and_now(
    actor_id: UUID,
    source: VisitStatus,
    now: datetime,
) -> None:
    """A checked-in actor emits one VisitCheckedOut keyed on state.id, actor, now."""
    state = _state_with_open_entry(
        actor_id=actor_id,
        check_in_at=now - timedelta(hours=2),
        status=source,
    )
    result = decide(
        state=state,
        command=CheckOutVisit(visit_id=VISIT_ID, actor_id=actor_id),
        now=now,
    )
    assert result == [VisitCheckedOut(visit_id=state.id, actor_id=actor_id, occurred_at=now)]


@pytest.mark.unit
@given(actor_id=st.uuids(), now=aware_datetimes())
def test_check_out_is_pure_same_input_same_output(
    actor_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock leakage)."""
    state = _state_with_open_entry(actor_id=actor_id, check_in_at=now - timedelta(hours=1))
    command = CheckOutVisit(visit_id=VISIT_ID, actor_id=actor_id)
    first = decide(state=state, command=command, now=now)
    second = decide(state=state, command=command, now=now)
    assert first == second
