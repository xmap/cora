"""Property-based tests for `decommission_facility.decide` (Federation BC).

Mirrors the Access / Trust / Federation decider-PBT pattern. Universal
claims across generated inputs:

  - state=None always raises FacilityNotFoundError.
  - state.status=Decommissioned always raises FacilityCannotDecommissionError.
  - state.status=Active emits exactly one FacilityDecommissioned with
    the injected now / decommissioned_by and the command's reason.
  - Pure: same (state, command, now, decommissioned_by) returns the
    same events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotDecommissionError,
    FacilityKind,
    FacilityName,
    FacilityNotFoundError,
    FacilityStatus,
)
from cora.federation.features import decommission_facility
from cora.federation.features.decommission_facility import DecommissionFacility
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID

_CODE = FacilityCode("aps-site")
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_REASON = printable_ascii_text(min_size=0, max_size=200) | st.none()


def _facility(
    facility_id: UUID,
    actor_id: UUID,
    *,
    status: FacilityStatus,
) -> Facility:
    return Facility(
        id=FacilityId(facility_id),
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=status,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=ActorId(actor_id),
        decommissioned_at=None if status is FacilityStatus.ACTIVE else _REGISTERED_AT,
        decommissioned_by=None if status is FacilityStatus.ACTIVE else ActorId(actor_id),
    )


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_facility_on_none_state_always_raises_not_found(
    facility_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state=None -> FacilityNotFoundError, regardless of command."""
    command = DecommissionFacility(
        facility_id=FacilityId(facility_id),
        reason=reason,
    )
    with pytest.raises(FacilityNotFoundError) as exc:
        decommission_facility.decide(
            state=None,
            command=command,
            now=now,
            decommissioned_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_facility_on_decommissioned_state_always_raises_cannot(
    facility_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Decommissioned -> FacilityCannotDecommissionError, always."""
    state = _facility(facility_id, actor_id, status=FacilityStatus.DECOMMISSIONED)
    command = DecommissionFacility(
        facility_id=FacilityId(facility_id),
        reason=reason,
    )
    with pytest.raises(FacilityCannotDecommissionError) as exc:
        decommission_facility.decide(
            state=state,
            command=command,
            now=now,
            decommissioned_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_facility_on_active_state_emits_single_event(
    facility_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Active -> single FacilityDecommissioned with injected fields."""
    state = _facility(facility_id, actor_id, status=FacilityStatus.ACTIVE)
    command = DecommissionFacility(
        facility_id=FacilityId(facility_id),
        reason=reason,
    )
    events = decommission_facility.decide(
        state=state,
        command=command,
        now=now,
        decommissioned_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == facility_id
    assert event.decommissioned_by == actor_id
    assert event.occurred_at == now
    assert event.reason == reason


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_decommission_facility_is_pure_same_input_same_output(
    facility_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events."""
    state = _facility(facility_id, actor_id, status=FacilityStatus.ACTIVE)
    command = DecommissionFacility(
        facility_id=FacilityId(facility_id),
        reason=reason,
    )
    first = decommission_facility.decide(
        state=state, command=command, now=now, decommissioned_by=ActorId(actor_id)
    )
    second = decommission_facility.decide(
        state=state, command=command, now=now, decommissioned_by=ActorId(actor_id)
    )
    assert first == second
