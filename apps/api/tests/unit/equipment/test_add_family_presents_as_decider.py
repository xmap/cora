"""Unit tests for the `add_family_presents_as` slice's pure decider."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family import (
    Affordance,
    Family,
    FamilyCannotPresentAsError,
    FamilyName,
    FamilyNotFoundError,
    FamilyPresentsAsAdded,
    FamilyRolePresentsAsAlreadyError,
)
from cora.equipment.features import add_family_presents_as
from cora.equipment.features.add_family_presents_as import AddFamilyPresentsAs
from cora.infrastructure.ports.role_lookup import RoleLookupResult

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _family(
    *,
    family_id: UUID,
    affordances: frozenset[Affordance],
    presents_as: frozenset[RoleId] = frozenset(),
) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("Camera"),
        affordances=affordances,
        presents_as=presents_as,
    )


def _role_lookup(
    role_id: UUID,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> RoleLookupResult:
    return RoleLookupResult(
        id=role_id,
        name="Detector",
        required_affordances=required,
        optional_affordances=optional,
    )


@pytest.mark.unit
def test_decide_emits_event_when_family_covers_required_affordances() -> None:
    fid = uuid4()
    rid = uuid4()
    events = add_family_presents_as.decide(
        state=_family(family_id=fid, affordances=frozenset({Affordance.IMAGEABLE})),
        command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
        now=_NOW,
        role_lookup_result=_role_lookup(rid, required=frozenset({"Imageable"})),
    )
    assert events == [FamilyPresentsAsAdded(family_id=fid, role_id=rid, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(FamilyNotFoundError) as exc:
        add_family_presents_as.decide(
            state=None,
            command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
            now=_NOW,
            role_lookup_result=_role_lookup(rid, required=frozenset()),
        )
    assert exc.value.family_id == fid


@pytest.mark.unit
def test_decide_rejects_when_role_already_advertised() -> None:
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(FamilyRolePresentsAsAlreadyError) as exc:
        add_family_presents_as.decide(
            state=_family(
                family_id=fid,
                affordances=frozenset({Affordance.IMAGEABLE}),
                presents_as=frozenset({RoleId(rid)}),
            ),
            command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
            now=_NOW,
            role_lookup_result=_role_lookup(rid, required=frozenset({"Imageable"})),
        )
    assert exc.value.family_id == fid
    assert exc.value.role_id == rid


@pytest.mark.unit
def test_decide_rejects_when_family_missing_required_affordances() -> None:
    """Family.affordances={Imageable} cannot present a Role requiring
    {Imageable, Binnable}: missing_affordances surfaces in the error."""
    fid = uuid4()
    rid = uuid4()
    with pytest.raises(FamilyCannotPresentAsError) as exc:
        add_family_presents_as.decide(
            state=_family(family_id=fid, affordances=frozenset({Affordance.IMAGEABLE})),
            command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
            now=_NOW,
            role_lookup_result=_role_lookup(rid, required=frozenset({"Imageable", "Binnable"})),
        )
    assert exc.value.family_id == fid
    assert exc.value.role_id == rid
    assert exc.value.missing_affordances == frozenset({Affordance.BINNABLE})


@pytest.mark.unit
def test_decide_accepts_when_role_requires_no_affordances() -> None:
    """Empty required_affordances trivially satisfied by any Family."""
    fid = uuid4()
    rid = uuid4()
    events = add_family_presents_as.decide(
        state=_family(family_id=fid, affordances=frozenset()),
        command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
        now=_NOW,
        role_lookup_result=_role_lookup(rid, required=frozenset()),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_when_family_has_extra_affordances() -> None:
    """Superset is fine: Family.affordances may exceed required_affordances."""
    fid = uuid4()
    rid = uuid4()
    events = add_family_presents_as.decide(
        state=_family(
            family_id=fid,
            affordances=frozenset({Affordance.IMAGEABLE, Affordance.BINNABLE, Affordance.COOLABLE}),
        ),
        command=AddFamilyPresentsAs(family_id=fid, role_id=rid),
        now=_NOW,
        role_lookup_result=_role_lookup(rid, required=frozenset({"Imageable"})),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_handler_contract_assert_fires_on_role_id_mismatch() -> None:
    """Defensive: a handler that loaded the wrong RoleLookupResult
    triggers an AssertionError. Never user-driven, but caught at the
    decider boundary."""
    fid = uuid4()
    cmd_rid = uuid4()
    lookup_rid = uuid4()
    with pytest.raises(AssertionError):
        add_family_presents_as.decide(
            state=_family(family_id=fid, affordances=frozenset({Affordance.IMAGEABLE})),
            command=AddFamilyPresentsAs(family_id=fid, role_id=cmd_rid),
            now=_NOW,
            role_lookup_result=_role_lookup(lookup_rid, required=frozenset()),
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    fid = uuid4()
    rid = uuid4()
    state = _family(family_id=fid, affordances=frozenset({Affordance.IMAGEABLE}))
    cmd = AddFamilyPresentsAs(family_id=fid, role_id=rid)
    lookup = _role_lookup(rid, required=frozenset({"Imageable"}))
    first = add_family_presents_as.decide(
        state=state, command=cmd, now=_NOW, role_lookup_result=lookup
    )
    second = add_family_presents_as.decide(
        state=state, command=cmd, now=_NOW, role_lookup_result=lookup
    )
    assert first == second
