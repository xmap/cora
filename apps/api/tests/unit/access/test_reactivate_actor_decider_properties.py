"""Property-based tests for `reactivate_actor.decide` (Access BC).

Mirror of `test_deactivate_actor_decider_properties.py`, pinning the
same universal shape on the inverse command:

  - state=None -> ActorNotFoundError, always.
  - state.active=True -> ActorCannotReactivateError, always.
  - state.active=False -> single ActorReactivated whose actor_id is
    state.id (NOT command.actor_id, the same load-bearing distinction
    the deactivate sibling pins).
  - Pure: same (state, command, now) -> same events.

Plus the one property that is this slice's whole reason for existing
and has no sibling: deactivate followed by reactivate returns the
aggregate to active, preserving id and kind. That is the reversibility
claim itself, so it is asserted through the evolver rather than
inferred from the decider's return value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ActorCannotReactivateError,
    ActorDeactivated,
    ActorKind,
    ActorNotFoundError,
    ActorReactivated,
    ActorRegistered,
    fold,
)
from cora.access.features import reactivate_actor
from cora.access.features.reactivate_actor import ReactivateActor

_KIND = st.sampled_from(list(ActorKind))
_DATETIME = st.datetimes()


def _actor(
    actor_id: UUID,
    *,
    active: bool = False,
    kind: ActorKind = ActorKind.HUMAN,
) -> Actor:
    return Actor(id=actor_id, active=active, kind=kind)


@pytest.mark.unit
@given(actor_id=st.uuids(), now=_DATETIME)
def test_reactivate_with_none_state_always_raises_not_found(actor_id: UUID, now: datetime) -> None:
    with pytest.raises(ActorNotFoundError) as exc:
        reactivate_actor.decide(
            state=None,
            command=ReactivateActor(actor_id=actor_id),
            now=now,
        )
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    command_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_reactivate_active_state_always_raises_already_active(
    actor_id: UUID, command_id: UUID, kind: ActorKind, now: datetime
) -> None:
    """Already-active state rejects regardless of which id the command targets."""
    with pytest.raises(ActorCannotReactivateError) as exc:
        reactivate_actor.decide(
            state=_actor(actor_id, active=True, kind=kind),
            command=ReactivateActor(actor_id=command_id),
            now=now,
        )
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    command_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_reactivate_inactive_actor_emits_event_with_state_id(
    actor_id: UUID, command_id: UUID, kind: ActorKind, now: datetime
) -> None:
    """Emitted event uses STATE.id, not command.actor_id."""
    events = reactivate_actor.decide(
        state=_actor(actor_id, active=False, kind=kind),
        command=ReactivateActor(actor_id=command_id),
        now=now,
    )
    assert events == [ActorReactivated(actor_id=actor_id, occurred_at=now)]


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_reactivate_is_pure_same_input_same_output(
    actor_id: UUID, kind: ActorKind, now: datetime
) -> None:
    state = _actor(actor_id, active=False, kind=kind)
    command = ReactivateActor(actor_id=actor_id)
    first = reactivate_actor.decide(state=state, command=command, now=now)
    second = reactivate_actor.decide(state=state, command=command, now=now)
    assert first == second


@pytest.mark.unit
@given(actor_id=st.uuids(), kind=_KIND, now=_DATETIME)
def test_deactivate_then_reactivate_restores_the_registered_actor(
    actor_id: UUID, kind: ActorKind, now: datetime
) -> None:
    """The reversibility claim, asserted end to end through the evolver.

    An Agent's operator pause has always been reversible via
    resume_agent. Folding registration, deactivation, and reactivation
    must land on exactly the state registration produced, so a
    mis-issued deactivation leaves no residue on id, kind, or
    availability.
    """
    registered = Actor(id=actor_id, kind=kind)
    round_tripped = fold(
        [
            ActorRegistered(actor_id=actor_id, occurred_at=now, kind=kind),
            ActorDeactivated(actor_id=actor_id, occurred_at=now),
            ActorReactivated(actor_id=actor_id, occurred_at=now),
        ]
    )
    assert round_tripped == registered
