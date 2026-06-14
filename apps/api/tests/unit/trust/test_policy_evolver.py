"""Unit tests for the Policy aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.aggregates.policy import Policy, PolicyName, evolve, fold
from cora.trust.aggregates.policy.events import PolicyDefined
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_policy_defined_from_empty_state() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    p1 = uuid4()
    state = evolve(
        None,
        PolicyDefined(
            policy_id=policy_id,
            name="Beam-team",
            conduit_id=conduit,
            permitted_principal_ids=(p1,),
            permitted_commands=("RegisterActor",),
            occurred_at=_NOW,
        ),
    )
    assert state == Policy(
        id=policy_id,
        name=PolicyName("Beam-team"),
        conduit_id=conduit,
        permitted_principal_ids=frozenset({p1}),
        permitted_commands=frozenset({"RegisterActor"}),
    )


@pytest.mark.unit
def test_evolve_converts_lists_to_frozensets() -> None:
    """Event payloads carry lists (JSON primitives); state holds frozensets
    (set semantics for evaluate's O(1) lookups). Pin the bridge."""
    policy_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    state = evolve(
        None,
        PolicyDefined(
            policy_id=policy_id,
            name="X",
            conduit_id=uuid4(),
            permitted_principal_ids=(p1, p2, p1),  # duplicate intentionally
            permitted_commands=("A", "B", "A"),
            occurred_at=_NOW,
        ),
    )
    assert state.permitted_principal_ids == frozenset({p1, p2})
    assert state.permitted_commands == frozenset({"A", "B"})


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_policy_defined_returns_policy() -> None:
    policy_id = uuid4()
    conduit = uuid4()
    state = fold(
        [
            PolicyDefined(
                policy_id=policy_id,
                name="Beam-team",
                conduit_id=conduit,
                permitted_principal_ids=(),
                permitted_commands=(),
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Policy(
        id=policy_id,
        name=PolicyName("Beam-team"),
        conduit_id=conduit,
        permitted_principal_ids=frozenset(),
        permitted_commands=frozenset(),
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    events = [
        PolicyDefined(
            policy_id=uuid4(),
            name="X",
            conduit_id=uuid4(),
            permitted_principal_ids=(uuid4(),),
            permitted_commands=("X",),
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    conduit = uuid4()
    p1, p2 = uuid4(), uuid4()
    command = DefinePolicy(
        name="  Beam-team  ",  # whitespace exercises the VO trim
        conduit_id=conduit,
        permitted_principal_ids=frozenset({p1, p2}),
        permitted_commands=frozenset({"RegisterActor", "DefineZone"}),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )

    events = define_policy.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Policy(
        id=new_id,
        name=PolicyName("Beam-team"),
        conduit_id=conduit,
        permitted_principal_ids=frozenset({p1, p2}),
        permitted_commands=frozenset({"RegisterActor", "DefineZone"}),
        surface_id=SYSTEM_HTTP_SURFACE_ID,
    )
