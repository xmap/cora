"""Decider tests for `close_visit_presence` (closing another actor's entry)."""

from dataclasses import replace
from uuid import uuid4

import pytest

from cora.trust.aggregates.visit import (
    PresenceEntry,
    PresenceMode,
    VisitActorNotCheckedInError,
    VisitNotFoundError,
    VisitPresenceClosed,
    VisitStatus,
)
from cora.trust.features.close_visit_presence import CloseVisitPresence
from cora.trust.features.close_visit_presence.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


def _with_open_entry(actor_id: object) -> object:
    base = make_visit(VisitStatus.IN_PROGRESS)
    return replace(
        base,
        presence_entries=frozenset(
            {
                PresenceEntry(
                    actor_id=actor_id,  # pyright: ignore[reportArgumentType]
                    mode=PresenceMode.PHYSICAL,
                    check_in_at=NOW,
                    check_out_at=None,
                )
            }
        ),
    )


@pytest.mark.unit
def test_close_presence_closes_the_named_actors_entry_not_the_callers() -> None:
    """The command names its target; the caller is not the subject.

    This is the axis on which the slice differs from check_out_visit, so it is
    the one worth pinning: a caller closing somebody else's entry must produce
    an event naming THAT actor.
    """
    absent_actor = uuid4()
    events = decide(
        state=_with_open_entry(absent_actor),  # pyright: ignore[reportArgumentType]
        command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=absent_actor),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitPresenceClosed)
    assert e.actor_id == absent_actor


@pytest.mark.unit
def test_close_presence_raises_when_named_actor_has_no_open_entry() -> None:
    someone_present = uuid4()
    someone_else = uuid4()
    with pytest.raises(VisitActorNotCheckedInError) as exc:
        decide(
            state=_with_open_entry(someone_present),  # pyright: ignore[reportArgumentType]
            command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=someone_else),
            now=NOW,
        )
    assert exc.value.actor_id == someone_else


@pytest.mark.unit
def test_close_presence_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(
            state=None,
            command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=uuid4()),
            now=NOW,
        )


@pytest.mark.unit
def test_close_presence_is_not_blocked_by_a_terminal_visit_status() -> None:
    """No status guard: the evolver has already closed entries on a terminal
    Visit, so an open entry here means the Visit is still live."""
    actor = uuid4()
    events = decide(
        state=_with_open_entry(actor),  # pyright: ignore[reportArgumentType]
        command=CloseVisitPresence(visit_id=VISIT_ID, actor_id=actor),
        now=NOW,
    )
    assert len(events) == 1
