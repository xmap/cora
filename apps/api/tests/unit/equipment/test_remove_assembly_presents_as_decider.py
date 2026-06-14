"""Unit tests for the `remove_assembly_presents_as` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.assembly import (
    Assembly,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyPresentsAsRemoved,
    AssemblyRolePresentsAsNotPresentError,
)
from cora.equipment.features import remove_assembly_presents_as
from cora.equipment.features.remove_assembly_presents_as import RemoveAssemblyPresentsAs

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _assembly(
    *,
    assembly_id: UUID,
    presents_as: frozenset[RoleId] = frozenset(),
) -> Assembly:
    return Assembly(
        id=assembly_id,
        name=AssemblyName("Microscope"),
        presents_as_family_id=uuid4(),
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_emits_event_when_role_is_advertised() -> None:
    aid = uuid4()
    rid = uuid4()
    events = remove_assembly_presents_as.decide(
        state=_assembly(assembly_id=aid, presents_as=frozenset({RoleId(rid)})),
        command=RemoveAssemblyPresentsAs(assembly_id=aid, role_id=rid),
        now=_NOW,
    )
    assert events == [AssemblyPresentsAsRemoved(assembly_id=aid, role_id=rid, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    aid = uuid4()
    rid = uuid4()
    with pytest.raises(AssemblyNotFoundError) as exc:
        remove_assembly_presents_as.decide(
            state=None,
            command=RemoveAssemblyPresentsAs(assembly_id=aid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.assembly_id == aid


@pytest.mark.unit
def test_decide_rejects_when_role_not_present_strict_not_idempotent() -> None:
    aid = uuid4()
    rid = uuid4()
    with pytest.raises(AssemblyRolePresentsAsNotPresentError) as exc:
        remove_assembly_presents_as.decide(
            state=_assembly(assembly_id=aid, presents_as=frozenset()),
            command=RemoveAssemblyPresentsAs(assembly_id=aid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.assembly_id == aid
    assert exc.value.role_id == rid


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    aid = uuid4()
    rid = uuid4()
    state = _assembly(assembly_id=aid, presents_as=frozenset({RoleId(rid)}))
    cmd = RemoveAssemblyPresentsAs(assembly_id=aid, role_id=rid)
    first = remove_assembly_presents_as.decide(state=state, command=cmd, now=_NOW)
    second = remove_assembly_presents_as.decide(state=state, command=cmd, now=_NOW)
    assert first == second
