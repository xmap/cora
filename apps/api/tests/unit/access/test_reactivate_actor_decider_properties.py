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
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime

from datetime import UTC
from datetime import datetime as _dt

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
from cora.access.errors import ActorSelfReactivationRefusedError
from cora.access.features import reactivate_actor
from cora.access.features.reactivate_actor import ReactivateActor
from cora.access.features.reactivate_actor.decider import decide

_NOW = _dt(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
# A caller distinct from the actor under test. The decider refuses
# self-reactivation, so every property here must be asked by somebody
# else; `assume` keeps the generated actor id from colliding with it.
_OPERATOR_ID = UUID("01900000-0000-7000-8000-00000000d001")
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
    assume(actor_id != _OPERATOR_ID)
    with pytest.raises(ActorNotFoundError) as exc:
        reactivate_actor.decide(
            state=None,
            command=ReactivateActor(actor_id=actor_id),
            now=now,
            principal_id=_OPERATOR_ID,
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
    assume(actor_id != _OPERATOR_ID)
    with pytest.raises(ActorCannotReactivateError) as exc:
        reactivate_actor.decide(
            state=_actor(actor_id, active=True, kind=kind),
            command=ReactivateActor(actor_id=command_id),
            now=now,
            principal_id=_OPERATOR_ID,
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
    assume(actor_id != _OPERATOR_ID)
    events = reactivate_actor.decide(
        state=_actor(actor_id, active=False, kind=kind),
        command=ReactivateActor(actor_id=command_id),
        now=now,
        principal_id=_OPERATOR_ID,
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
    assume(actor_id != _OPERATOR_ID)
    state = _actor(actor_id, active=False, kind=kind)
    command = ReactivateActor(actor_id=actor_id)
    first = reactivate_actor.decide(
        state=state, command=command, now=now, principal_id=_OPERATOR_ID
    )
    second = reactivate_actor.decide(
        state=state, command=command, now=now, principal_id=_OPERATOR_ID
    )
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


@pytest.mark.unit
def test_self_reactivation_is_refused_before_the_already_active_check() -> None:
    """Nobody reinstates themselves, and the order of the two guards matters.

    The self check runs BEFORE the already-active one so the refusal is
    the same whatever state the caller's own Actor is in. Were it second,
    a deactivated principal asking about itself would get
    `ActorSelfReactivationRefusedError` while an active one got
    `ActorCannotReactivateError`, turning the error type into a probe for
    your own switch.
    """
    actor_id = UUID("01900000-0000-7000-8000-0000000000c1")

    for active in (True, False):
        with pytest.raises(ActorSelfReactivationRefusedError):
            decide(
                Actor(id=actor_id, active=active),
                ReactivateActor(actor_id=actor_id),
                now=_NOW,
                principal_id=actor_id,
            )


@pytest.mark.unit
def test_another_principal_may_reactivate_a_deactivated_actor() -> None:
    """The guard must not break the case the slice exists for."""
    actor_id = UUID("01900000-0000-7000-8000-0000000000c1")
    operator_id = UUID("01900000-0000-7000-8000-0000000000c2")

    events = decide(
        Actor(id=actor_id, active=False),
        ReactivateActor(actor_id=actor_id),
        now=_NOW,
        principal_id=operator_id,
    )

    assert [e.actor_id for e in events] == [actor_id]
