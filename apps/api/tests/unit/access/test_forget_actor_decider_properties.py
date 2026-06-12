"""Property-based tests for `forget_actor.decide` (Access BC).

Complements the example-based `test_forget_actor_decider.py` with
universal claims across generated inputs. The decider is pure

    (state, command, now) -> list[ActorProfileForgotten]

PII-erasure has no source-state guard beyond existence (and is
intentionally non-idempotent at the event level), so the universal
claims are:

  - state=None always raises `ActorNotFoundError` carrying
    command.actor_id.
  - Any non-None state (regardless of active flag or kind) emits
    exactly one `ActorProfileForgotten` carrying state.id and
    occurred_at=now.
  - The emitted event's actor_id is `state.id`, never command.actor_id.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.access.aggregates.actor import (
    Actor,
    ActorKind,
    ActorNotFoundError,
    ActorProfileForgotten,
)
from cora.access.features import forget_actor
from cora.access.features.forget_actor import ForgetActor
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_KIND = st.sampled_from(list(ActorKind))


def _actor(*, actor_id: UUID, active: bool, kind: ActorKind) -> Actor:
    return Actor(id=actor_id, active=active, kind=kind)


@pytest.mark.unit
@given(actor_id=st.uuids(), now=aware_datetimes())
def test_forget_with_none_state_always_raises_not_found(
    actor_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `ActorNotFoundError` carrying command.actor_id."""
    with pytest.raises(ActorNotFoundError) as exc:
        forget_actor.decide(state=None, command=ForgetActor(actor_id=actor_id), now=now)
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(actor_id=st.uuids(), active=st.booleans(), kind=_KIND, now=aware_datetimes())
def test_forget_existing_actor_emits_single_event_regardless_of_state(
    actor_id: UUID,
    active: bool,
    kind: ActorKind,
    now: datetime,
) -> None:
    """Any existing Actor (any active flag / kind) emits one ActorProfileForgotten."""
    events = forget_actor.decide(
        state=_actor(actor_id=actor_id, active=active, kind=kind),
        command=ForgetActor(actor_id=actor_id),
        now=now,
    )
    assert events == [ActorProfileForgotten(actor_id=actor_id, occurred_at=now)]


@pytest.mark.unit
@given(state_actor_id=st.uuids(), command_actor_id=st.uuids(), now=aware_datetimes())
def test_forget_uses_state_id_not_command_actor_id(
    state_actor_id: UUID,
    command_actor_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's actor_id is state.id, not command.actor_id."""
    assume(state_actor_id != command_actor_id)
    events = forget_actor.decide(
        state=_actor(actor_id=state_actor_id, active=True, kind=ActorKind.HUMAN),
        command=ForgetActor(actor_id=command_actor_id),
        now=now,
    )
    assert events[0].actor_id == state_actor_id


@pytest.mark.unit
@given(actor_id=st.uuids(), now=aware_datetimes())
def test_forget_is_pure_same_input_same_output(actor_id: UUID, now: datetime) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _actor(actor_id=actor_id, active=True, kind=ActorKind.HUMAN)
    command = ForgetActor(actor_id=actor_id)
    first = forget_actor.decide(state=state, command=command, now=now)
    second = forget_actor.decide(state=state, command=command, now=now)
    assert first == second
