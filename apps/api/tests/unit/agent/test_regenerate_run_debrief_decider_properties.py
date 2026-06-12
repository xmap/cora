"""Property-based tests for `regenerate_run_debrief.decide` (Agent BC).

Complements the handler test (`test_regenerate_run_debrief_handler.py`,
which pins the cross-aggregate pre-load gates) with universal claims
across generated inputs. `regenerate_run_debrief.decide` is a bespoke
genesis-with-context decider: it ignores `state` (always None at the
handler) and composes a single `DecisionRegistered` from the handler-
built `RegenerateRunDebriefContext`. The full validation matrix lives in
the Decision BC's own tests; the PBT asserts the universal claims that
hold across the whole input space:

  - Happy path always emits exactly one `DecisionRegistered` carrying the
    injected ids: decision_id=new_id, occurred_at=now,
    decided_by=ActorId(context.actor.id), context="RunDebrief",
    choice threaded through, parent_id=command.parent_decision_id.
  - The base `inputs` always carry run_id (str of command.run_id),
    trigger="on-demand", and the prompt_template_id discriminator.
  - State is ignored: any non-None state yields the same single event
    (genesis signature parity, no existence guard).
  - parent_decision_id threads straight through (set or None).
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.access.aggregates.actor import Actor, ActorKind
from cora.agent.features.regenerate_run_debrief.command import RegenerateRunDebrief
from cora.agent.features.regenerate_run_debrief.context import RegenerateRunDebriefContext
from cora.agent.features.regenerate_run_debrief.decider import decide
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    Decision,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_CHOICE = "NominalCompletion"
_CONFIDENCE = 0.88
_REASONING = (
    "On-demand debrief regeneration: Run completed nominally. The scan ran "
    "to RunCompleted with effective_parameters matching defaults."
)


def _actor(actor_id: UUID) -> Actor:
    return Actor(id=actor_id, active=True, kind=ActorKind.AGENT)


def _context(*, actor_id: UUID) -> RegenerateRunDebriefContext:
    return RegenerateRunDebriefContext(
        actor=_actor(actor_id),
        choice=_CHOICE,
        confidence=_CONFIDENCE,
        reasoning=_REASONING,
    )


def _command(*, run_id: UUID, parent_decision_id: UUID | None = None) -> RegenerateRunDebrief:
    return RegenerateRunDebrief(run_id=run_id, parent_decision_id=parent_decision_id)


def _state(*, state_id: UUID, now: datetime) -> Decision:
    return Decision(
        id=state_id,
        decided_by=ActorId(UUID(int=1)),
        decided_at=now,
        context=DecisionContext(DECISION_CONTEXT_RUN_DEBRIEF),
        choice=DecisionChoice("PriorChoice"),
    )


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    actor_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_happy_path_emits_single_decision_with_injected_ids(
    run_id: UUID,
    actor_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """The happy path emits one DecisionRegistered with new_id, now, and threaded fields."""
    events = decide(
        None,
        _command(run_id=run_id),
        context=_context(actor_id=actor_id),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, DecisionRegistered)
    assert event.decision_id == new_id
    assert event.occurred_at == now
    assert event.decided_by == ActorId(actor_id)
    assert event.context == DECISION_CONTEXT_RUN_DEBRIEF
    assert event.choice == _CHOICE
    assert event.confidence == _CONFIDENCE
    assert event.confidence_source == DecisionConfidenceSource.SELF_REPORTED
    assert event.parent_id is None


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    actor_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_always_threads_base_inputs(
    run_id: UUID,
    actor_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """The base inputs always carry run_id, trigger, and prompt_template_id."""
    events = decide(
        None,
        _command(run_id=run_id),
        context=_context(actor_id=actor_id),
        now=now,
        new_id=new_id,
    )
    inputs = events[0].inputs
    assert inputs is not None
    assert inputs["run_id"] == str(run_id)
    assert inputs["trigger"] == "on-demand"
    assert inputs["prompt_template_id"] == str(RUN_DEBRIEF_PROMPT_TEMPLATE_ID)


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    actor_id=st.uuids(),
    parent_decision_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_threads_parent_decision_id_through(
    run_id: UUID,
    actor_id: UUID,
    parent_decision_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """A supplied parent_decision_id always becomes the event's parent_id."""
    events = decide(
        None,
        _command(run_id=run_id, parent_decision_id=parent_decision_id),
        context=_context(actor_id=actor_id),
        now=now,
        new_id=new_id,
    )
    assert events[0].parent_id == parent_decision_id


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    actor_id=st.uuids(),
    state_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_ignores_non_none_state_genesis_parity(
    run_id: UUID,
    actor_id: UUID,
    state_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """A non-None state is accepted for signature parity and does not affect output."""
    command = _command(run_id=run_id)
    context = _context(actor_id=actor_id)
    with_state = decide(
        _state(state_id=state_id, now=now),
        command,
        context=context,
        now=now,
        new_id=new_id,
    )
    without_state = decide(
        None,
        command,
        context=context,
        now=now,
        new_id=new_id,
    )
    assert with_state == without_state


@pytest.mark.unit
@given(
    run_id=st.uuids(),
    actor_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_decide_is_pure_same_input_same_output(
    run_id: UUID,
    actor_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    command = _command(run_id=run_id)
    context = _context(actor_id=actor_id)
    first = decide(None, command, context=context, now=now, new_id=new_id)
    second = decide(None, command, context=context, now=now, new_id=new_id)
    assert first == second
