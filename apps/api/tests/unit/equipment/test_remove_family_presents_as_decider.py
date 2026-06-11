"""Unit tests for the `remove_family_presents_as` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyName,
    FamilyNotFoundError,
    FamilyPresentsAsRemoved,
    FamilyRolePresentsAsNotPresentError,
)
from cora.equipment.features import remove_family_presents_as
from cora.equipment.features.remove_family_presents_as import RemoveFamilyPresentsAs

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _family(
    *,
    family_id: UUID,
    presents_as: frozenset[RoleId] = frozenset(),
) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("Camera"),
        affordances=frozenset({Affordance.IMAGEABLE}),
        presents_as=presents_as,
    )


@pytest.mark.unit
def test_decide_emits_event_when_role_is_advertised() -> None:
    fid = uuid4()
    rid = uuid4()
    events = remove_family_presents_as.decide(
        state=_family(family_id=fid, presents_as=frozenset({RoleId(rid)})),
        command=RemoveFamilyPresentsAs(family_id=fid, role_id=rid),
        now=_NOW,
    )
    assert events == [FamilyPresentsAsRemoved(family_id=fid, role_id=rid, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(FamilyNotFoundError) as exc:
        remove_family_presents_as.decide(
            state=None,
            command=RemoveFamilyPresentsAs(family_id=fid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.family_id == fid


@pytest.mark.unit
def test_decide_rejects_when_role_not_present_strict_not_idempotent() -> None:
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(FamilyRolePresentsAsNotPresentError) as exc:
        remove_family_presents_as.decide(
            state=_family(family_id=fid, presents_as=frozenset()),
            command=RemoveFamilyPresentsAs(family_id=fid, role_id=rid),
            now=_NOW,
        )
    assert exc.value.family_id == fid
    assert exc.value.role_id == rid


@pytest.mark.unit
def test_decide_rejects_when_role_is_different_from_advertised_one() -> None:
    fid = uuid4()
    advertised = uuid4()
    requested = uuid4()
    with pytest.raises(FamilyRolePresentsAsNotPresentError):
        remove_family_presents_as.decide(
            state=_family(family_id=fid, presents_as=frozenset({RoleId(advertised)})),
            command=RemoveFamilyPresentsAs(family_id=fid, role_id=requested),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    fid = uuid4()
    rid = uuid4()
    state = _family(family_id=fid, presents_as=frozenset({RoleId(rid)}))
    cmd = RemoveFamilyPresentsAs(family_id=fid, role_id=rid)
    first = remove_family_presents_as.decide(state=state, command=cmd, now=_NOW)
    second = remove_family_presents_as.decide(state=state, command=cmd, now=_NOW)
    assert first == second
