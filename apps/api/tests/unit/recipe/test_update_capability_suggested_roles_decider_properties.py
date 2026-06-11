"""Property-based tests for `update_capability_suggested_roles.decide` (3E).

Universal claims:
  - state=None always raises CapabilityNotFoundError.
  - state.status=DEPRECATED always raises
    CapabilityCannotUpdateSuggestedRolesError.
  - state in {Defined, Versioned} always emits ONE event with the
    supplied set + injected now.
  - Pure: same inputs always produce the same outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotUpdateSuggestedRolesError,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilitySuggestedRolesUpdated,
)
from cora.recipe.features import update_capability_suggested_roles
from cora.recipe.features.update_capability_suggested_roles import (
    UpdateCapabilitySuggestedRoles,
)
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


def _capability(
    capability_id: UUID,
    *,
    status: CapabilityStatus = CapabilityStatus.DEFINED,
) -> Capability:
    return Capability(
        id=capability_id,
        code=CapabilityCode("cora.capability.acquire"),
        name=CapabilityName("Acquire"),
        status=status,
    )


_ROLE_SET = st.frozensets(st.uuids(), max_size=4)
_MUTABLE_STATUS = st.sampled_from([CapabilityStatus.DEFINED, CapabilityStatus.VERSIONED])


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    suggested_role_ids=_ROLE_SET,
    now=aware_datetimes(),
)
def test_state_none_always_raises_capability_not_found(
    capability_id: UUID,
    suggested_role_ids: frozenset[UUID],
    now: datetime,
) -> None:
    with pytest.raises(CapabilityNotFoundError):
        update_capability_suggested_roles.decide(
            state=None,
            command=UpdateCapabilitySuggestedRoles(
                capability_id=capability_id, suggested_role_ids=suggested_role_ids
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    suggested_role_ids=_ROLE_SET,
    now=aware_datetimes(),
)
def test_deprecated_always_raises_cannot_update(
    capability_id: UUID,
    suggested_role_ids: frozenset[UUID],
    now: datetime,
) -> None:
    state = _capability(capability_id, status=CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotUpdateSuggestedRolesError):
        update_capability_suggested_roles.decide(
            state=state,
            command=UpdateCapabilitySuggestedRoles(
                capability_id=capability_id, suggested_role_ids=suggested_role_ids
            ),
            now=now,
        )


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    suggested_role_ids=_ROLE_SET,
    status=_MUTABLE_STATUS,
    now=aware_datetimes(),
)
def test_mutable_status_always_emits_single_event(
    capability_id: UUID,
    suggested_role_ids: frozenset[UUID],
    status: CapabilityStatus,
    now: datetime,
) -> None:
    state = _capability(capability_id, status=status)
    events = update_capability_suggested_roles.decide(
        state=state,
        command=UpdateCapabilitySuggestedRoles(
            capability_id=capability_id, suggested_role_ids=suggested_role_ids
        ),
        now=now,
    )
    assert events == [
        CapabilitySuggestedRolesUpdated(
            capability_id=capability_id,
            suggested_role_ids=suggested_role_ids,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    capability_id=st.uuids(),
    suggested_role_ids=_ROLE_SET,
    status=_MUTABLE_STATUS,
    now=aware_datetimes(),
)
def test_decider_is_pure_same_input_same_output(
    capability_id: UUID,
    suggested_role_ids: frozenset[UUID],
    status: CapabilityStatus,
    now: datetime,
) -> None:
    state = _capability(capability_id, status=status)
    cmd = UpdateCapabilitySuggestedRoles(
        capability_id=capability_id, suggested_role_ids=suggested_role_ids
    )
    first = update_capability_suggested_roles.decide(state=state, command=cmd, now=now)
    second = update_capability_suggested_roles.decide(state=state, command=cmd, now=now)
    assert first == second
