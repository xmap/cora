"""Property-based tests for `add_facility_trust_anchor_credential.decide`.

Mirrors the Federation decider-PBT pattern. Universal claims across
generated inputs:

  - state=None always raises FacilityNotFoundError.
  - state.status=Decommissioned always raises
    FacilityCannotAddTrustAnchorCredentialError (lifecycle arm).
  - state.kind=Area always raises
    FacilityCannotAddTrustAnchorCredentialError (kind arm).
  - state.status=Active + kind=Site + credential already present
    raises FacilityTrustAnchorCredentialAlreadyPresentError.
  - state.status=Active + kind=Site + credential absent emits exactly
    one FacilityTrustAnchorCredentialAdded carrying the injected
    now / added_by.
  - Pure: same (state, command, now, added_by) returns the same events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityKind,
    FacilityName,
    FacilityNotFoundError,
    FacilityStatus,
    FacilityTrustAnchorCredentialAlreadyPresentError,
)
from cora.federation.features import add_facility_trust_anchor_credential
from cora.federation.features.add_facility_trust_anchor_credential import (
    AddFacilityTrustAnchorCredential,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from uuid import UUID

_CODE_SITE = FacilityCode("aps-site")
_CODE_AREA = FacilityCode("aps-area")
_PARENT_ID = FacilityId(__import__("uuid").UUID("01900000-0000-7000-8000-000000face01"))
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)


def _site_facility(
    facility_id: UUID,
    actor_id: UUID,
    *,
    status: FacilityStatus,
    trust_anchors: frozenset[CredentialId] = frozenset(),
) -> Facility:
    return Facility(
        id=FacilityId(facility_id),
        code=_CODE_SITE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=trust_anchors,
        status=status,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=ActorId(actor_id),
        decommissioned_at=None if status is FacilityStatus.ACTIVE else _REGISTERED_AT,
        decommissioned_by=None if status is FacilityStatus.ACTIVE else ActorId(actor_id),
    )


def _area_facility(facility_id: UUID, actor_id: UUID) -> Facility:
    return Facility(
        id=FacilityId(facility_id),
        code=_CODE_AREA,
        display_name=FacilityName("Beamline 2-BM"),
        kind=FacilityKind.AREA,
        parent_id=_PARENT_ID,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=ActorId(actor_id),
        decommissioned_at=None,
        decommissioned_by=None,
    )


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_on_none_state_always_raises_not_found(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state=None -> FacilityNotFoundError, regardless of command."""
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    with pytest.raises(FacilityNotFoundError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=None,
            command=command,
            now=now,
            added_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_on_decommissioned_always_raises_cannot(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Decommissioned -> FacilityCannotAddTrustAnchorCredentialError."""
    state = _site_facility(facility_id, actor_id, status=FacilityStatus.DECOMMISSIONED)
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=state,
            command=command,
            now=now,
            added_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_on_area_always_raises_cannot(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.kind=Area -> FacilityCannotAddTrustAnchorCredentialError."""
    state = _area_facility(facility_id, actor_id)
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=state,
            command=command,
            now=now,
            added_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_on_already_present_raises_already(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Active + kind=Site + present -> already-present error."""
    state = _site_facility(
        facility_id,
        actor_id,
        status=FacilityStatus.ACTIVE,
        trust_anchors=frozenset({CredentialId(credential_id)}),
    )
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    with pytest.raises(FacilityTrustAnchorCredentialAlreadyPresentError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=state,
            command=command,
            now=now,
            added_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_on_valid_state_emits_single_event(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Active Site + absent credential -> single Added event with injected fields."""
    state = _site_facility(facility_id, actor_id, status=FacilityStatus.ACTIVE)
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    events = add_facility_trust_anchor_credential.decide(
        state=state,
        command=command,
        now=now,
        added_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == facility_id
    assert event.credential_id == credential_id
    assert event.added_by == actor_id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_add_facility_trust_anchor_credential_is_pure_same_input_same_output(
    facility_id: UUID,
    credential_id: UUID,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events."""
    state = _site_facility(facility_id, actor_id, status=FacilityStatus.ACTIVE)
    command = AddFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
    )
    first = add_facility_trust_anchor_credential.decide(
        state=state, command=command, now=now, added_by=ActorId(actor_id)
    )
    second = add_facility_trust_anchor_credential.decide(
        state=state, command=command, now=now, added_by=ActorId(actor_id)
    )
    assert first == second
