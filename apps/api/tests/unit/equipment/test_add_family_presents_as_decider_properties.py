"""Property-based tests for `add_family_presents_as.decide`.

Universal claims:
  - State=None always raises FamilyNotFoundError, regardless of role.
  - Role already in presents_as always raises
    FamilyRolePresentsAsAlreadyError.
  - Role.required_affordances NOT subset of Family.affordances always
    raises FamilyCannotPresentAsError.
  - With valid disjoint inputs, emits a single FamilyPresentsAsAdded
    with the injected now.
  - Pure: same inputs always produce the same outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_AFFORDANCES = st.frozensets(st.sampled_from(list(Affordance)), max_size=4)


def _family(
    family_id: UUID,
    *,
    affordances: frozenset[Affordance],
    presents_as: frozenset[RoleId] = frozenset(),
) -> Family:
    return Family(
        id=family_id,
        name=FamilyName("X"),
        affordances=affordances,
        presents_as=presents_as,
    )


def _role_lookup(role_id: UUID, *, required: frozenset[str]) -> RoleLookupResult:
    return RoleLookupResult(
        id=role_id,
        name="X",
        required_affordances=required,
        optional_affordances=frozenset(),
    )


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    role_id=st.uuids(),
    family_affordances=_AFFORDANCES,
    now=aware_datetimes(),
)
def test_state_none_always_raises_family_not_found(
    family_id: UUID,
    role_id: UUID,
    family_affordances: frozenset[Affordance],
    now: datetime,
) -> None:
    affordance_values = frozenset(a.value for a in family_affordances)
    with pytest.raises(FamilyNotFoundError):
        add_family_presents_as.decide(
            state=None,
            command=AddFamilyPresentsAs(family_id=family_id, role_id=role_id),
            now=now,
            role_lookup_result=_role_lookup(role_id, required=affordance_values),
        )


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    role_id=st.uuids(),
    family_affordances=_AFFORDANCES,
    now=aware_datetimes(),
)
def test_role_already_advertised_always_raises(
    family_id: UUID,
    role_id: UUID,
    family_affordances: frozenset[Affordance],
    now: datetime,
) -> None:
    affordance_values = frozenset(a.value for a in family_affordances)
    state = _family(
        family_id,
        affordances=family_affordances,
        presents_as=frozenset({RoleId(role_id)}),
    )
    with pytest.raises(FamilyRolePresentsAsAlreadyError):
        add_family_presents_as.decide(
            state=state,
            command=AddFamilyPresentsAs(family_id=family_id, role_id=role_id),
            now=now,
            role_lookup_result=_role_lookup(role_id, required=affordance_values),
        )


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    role_id=st.uuids(),
    family_affordances=_AFFORDANCES,
    missing=st.sampled_from(list(Affordance)),
    now=aware_datetimes(),
)
def test_required_not_subset_always_raises_cannot_present(
    family_id: UUID,
    role_id: UUID,
    family_affordances: frozenset[Affordance],
    missing: Affordance,
    now: datetime,
) -> None:
    """Force missing Affordance to appear in required but NOT in Family."""
    family = family_affordances - {missing}
    required = (frozenset(a.value for a in family)) | {missing.value}
    state = _family(family_id, affordances=family)
    with pytest.raises(FamilyCannotPresentAsError) as exc:
        add_family_presents_as.decide(
            state=state,
            command=AddFamilyPresentsAs(family_id=family_id, role_id=role_id),
            now=now,
            role_lookup_result=_role_lookup(role_id, required=required),
        )
    assert missing in exc.value.missing_affordances


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    role_id=st.uuids(),
    family_affordances=_AFFORDANCES,
    now=aware_datetimes(),
)
def test_subset_required_emits_single_event(
    family_id: UUID,
    role_id: UUID,
    family_affordances: frozenset[Affordance],
    now: datetime,
) -> None:
    """Required subset of Family.affordances -> one event."""
    required = frozenset(a.value for a in family_affordances)
    state = _family(family_id, affordances=family_affordances)
    events = add_family_presents_as.decide(
        state=state,
        command=AddFamilyPresentsAs(family_id=family_id, role_id=role_id),
        now=now,
        role_lookup_result=_role_lookup(role_id, required=required),
    )
    assert events == [FamilyPresentsAsAdded(family_id=family_id, role_id=role_id, occurred_at=now)]


@pytest.mark.unit
@given(
    family_id=st.uuids(),
    role_id=st.uuids(),
    family_affordances=_AFFORDANCES,
    now=aware_datetimes(),
)
def test_decider_is_pure_same_input_same_output(
    family_id: UUID,
    role_id: UUID,
    family_affordances: frozenset[Affordance],
    now: datetime,
) -> None:
    required = frozenset(a.value for a in family_affordances)
    state = _family(family_id, affordances=family_affordances)
    cmd = AddFamilyPresentsAs(family_id=family_id, role_id=role_id)
    lookup = _role_lookup(role_id, required=required)
    first = add_family_presents_as.decide(
        state=state, command=cmd, now=now, role_lookup_result=lookup
    )
    second = add_family_presents_as.decide(
        state=state, command=cmd, now=now, role_lookup_result=lookup
    )
    assert first == second
