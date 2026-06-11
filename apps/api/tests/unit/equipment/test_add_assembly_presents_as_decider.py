"""Unit tests for the `add_assembly_presents_as` slice's pure decider.

Per 3C scope: the decider only enforces existence + strict-not-
idempotent. The affordance-superset gate is intentionally NOT
enforced here (deferred to register_fixture layer per memo Watch
item).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyPresentsAsAdded,
    AssemblyRolePresentsAsAlreadyError,
)
from cora.equipment.features import add_assembly_presents_as
from cora.equipment.features.add_assembly_presents_as import AddAssemblyPresentsAs

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _assembly(
    *,
    assembly_id: UUID,
    presents_as: frozenset[RoleId] = frozenset(),
) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("MCTOptics"),
        presents_as_family_id=uuid4(),
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_emits_event_when_role_not_advertised() -> None:
    aid = uuid4()
    rid = uuid4()
    events = add_assembly_presents_as.decide(
        state=_assembly(assembly_id=aid),
        command=AddAssemblyPresentsAs(assembly_id=aid, role_id=rid),
        now=_NOW,
    )
    assert events == [AssemblyPresentsAsAdded(assembly_id=aid, role_id=rid, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    aid = uuid4()
    rid = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc:
        add_assembly_presents_as.decide(
            state=None,
            command=AddAssemblyPresentsAs(assembly_id=aid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.assembly_id == aid


@pytest.mark.unit
def test_decide_rejects_when_role_already_advertised() -> None:
    aid = uuid4()
    rid = uuid4()
    with pytest.raises(AssemblyRolePresentsAsAlreadyError) as exc:
        add_assembly_presents_as.decide(
            state=_assembly(assembly_id=aid, presents_as=frozenset({RoleId(rid)})),
            command=AddAssemblyPresentsAs(assembly_id=aid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.assembly_id == aid
    assert exc.value.role_id == rid


@pytest.mark.unit
def test_decide_does_not_enforce_affordance_check() -> None:
    """3C deliberately skips the Family-style affordance-superset gate.

    Assembly affordances derive from constituent Family union at
    register_fixture time; this decider only sees the Assembly
    template stream and cannot know the constituent affordances.
    """
    aid = uuid4()
    rid = uuid4()
    # No Affordance machinery exists at this decider's input boundary
    # at all -- the absence of an AffordanceMismatchError test pins
    # the design choice.
    events = add_assembly_presents_as.decide(
        state=_assembly(assembly_id=aid),
        command=AddAssemblyPresentsAs(assembly_id=aid, role_id=rid),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    aid = uuid4()
    rid = uuid4()
    state = _assembly(assembly_id=aid)
    cmd = AddAssemblyPresentsAs(assembly_id=aid, role_id=rid)
    first = add_assembly_presents_as.decide(state=state, command=cmd, now=_NOW)
    second = add_assembly_presents_as.decide(state=state, command=cmd, now=_NOW)
    assert first == second
