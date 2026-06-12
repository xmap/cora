"""Property-based tests for `register_decision.decide` (Decision BC).

Complements the example-based `test_register_decision_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, context, now, new_id) -> list[DecisionRegistered]

Load-bearing properties:

  - Any non-None state always raises `DecisionAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - An AGENT-kind actor always raises `InvalidActorKindForDecisionError`
    (agent-emitted Decisions go through the signed subscriber path).
  - `override_kind` set with a None `parent_id` always raises
    `OverrideKindRequiresParentError`.
  - On the happy path the single `DecisionRegistered` carries the
    injected/passthrough fields: decision_id=new_id, decided_by,
    context, choice, parent_id=None, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.access.aggregates.actor import Actor, ActorKind
from cora.decision.aggregates.decision import (
    Decision,
    DecisionAlreadyExistsError,
    DecisionChoice,
    DecisionContext,
    DecisionOverrideKind,
    DecisionRegistered,
)
from cora.decision.errors import (
    InvalidActorKindForDecisionError,
    OverrideKindRequiresParentError,
)
from cora.decision.features import register_decision
from cora.decision.features.register_decision import (
    DecisionRegistrationContext,
    RegisterDecision,
)
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

_CONTEXT = printable_ascii_text(min_size=1, max_size=200)
_CHOICE = printable_ascii_text(min_size=1, max_size=500)
# DecisionOverrideKind is a Literal[...] alias (not a StrEnum), so it
# is not iterable; enumerate its values as a typed tuple to sample from.
_OVERRIDE_KINDS: tuple[DecisionOverrideKind, ...] = (
    "correction",
    "exception",
    "appeal",
    "supersession",
    "invalidation",
)
_OVERRIDE_KIND = st.sampled_from(_OVERRIDE_KINDS)
_FIXED_DECIDED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _command(
    *, decided_by: ActorId, context: str, choice: str, **overrides: object
) -> RegisterDecision:
    return RegisterDecision(decided_by=decided_by, context=context, choice=choice, **overrides)  # type: ignore[arg-type]


def _actor(*, kind: ActorKind = ActorKind.HUMAN) -> Actor:
    return Actor(id=UUID(int=7), active=True, kind=kind)


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    decided_by_uuid=st.uuids(),
    context=_CONTEXT,
    choice=_CHOICE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    decided_by_uuid: UUID,
    context: str,
    choice: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises DecisionAlreadyExistsError carrying state.id."""
    existing = Decision(
        id=existing_id,
        decided_by=ActorId(UUID(int=3)),
        decided_at=_FIXED_DECIDED_AT,
        context=DecisionContext("RecipeApproval"),
        choice=DecisionChoice("Approved"),
    )
    with pytest.raises(DecisionAlreadyExistsError) as exc:
        register_decision.decide(
            state=existing,
            command=_command(decided_by=ActorId(decided_by_uuid), context=context, choice=choice),
            context=DecisionRegistrationContext(actor=_actor()),
            now=now,
            new_id=new_id,
        )
    assert exc.value.decision_id == existing_id


@pytest.mark.unit
@given(
    decided_by_uuid=st.uuids(),
    context=_CONTEXT,
    choice=_CHOICE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_emits_single_event_with_injected_fields(
    decided_by_uuid: UUID,
    context: str,
    choice: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + non-agent actor emits one DecisionRegistered with injected fields."""
    decided_by = ActorId(decided_by_uuid)
    events = register_decision.decide(
        state=None,
        command=_command(decided_by=decided_by, context=context, choice=choice),
        context=DecisionRegistrationContext(actor=_actor()),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, DecisionRegistered)
    assert event.decision_id == new_id
    assert event.decided_by == decided_by
    assert event.context == context
    assert event.choice == choice
    assert event.parent_id is None
    assert event.override_kind is None
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    decided_by_uuid=st.uuids(),
    context=_CONTEXT,
    choice=_CHOICE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_with_agent_actor_always_raises_invalid_kind(
    decided_by_uuid: UUID,
    context: str,
    choice: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """An AGENT-kind actor is rejected (signed subscriber path only)."""
    with pytest.raises(InvalidActorKindForDecisionError):
        register_decision.decide(
            state=None,
            command=_command(decided_by=ActorId(decided_by_uuid), context=context, choice=choice),
            context=DecisionRegistrationContext(actor=_actor(kind=ActorKind.AGENT)),
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    decided_by_uuid=st.uuids(),
    context=_CONTEXT,
    choice=_CHOICE,
    override_kind=_OVERRIDE_KIND,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_override_without_parent_always_raises_requires_parent(
    decided_by_uuid: UUID,
    context: str,
    choice: str,
    override_kind: DecisionOverrideKind,
    now: datetime,
    new_id: UUID,
) -> None:
    """override_kind set with parent_id=None raises OverrideKindRequiresParentError."""
    with pytest.raises(OverrideKindRequiresParentError):
        register_decision.decide(
            state=None,
            command=_command(
                decided_by=ActorId(decided_by_uuid),
                context=context,
                choice=choice,
                parent_id=None,
                override_kind=override_kind,
            ),
            context=DecisionRegistrationContext(actor=_actor()),
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    decided_by_uuid=st.uuids(),
    context=_CONTEXT,
    choice=_CHOICE,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    decided_by_uuid: UUID,
    context: str,
    choice: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(decided_by=ActorId(decided_by_uuid), context=context, choice=choice)
    ctx = DecisionRegistrationContext(actor=_actor())
    first = register_decision.decide(
        state=None, command=command, context=ctx, now=now, new_id=new_id
    )
    second = register_decision.decide(
        state=None, command=command, context=ctx, now=now, new_id=new_id
    )
    assert first == second
