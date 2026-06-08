"""Property-based tests for `remove_facility_trust_anchor_credential.decide`.

Mirrors the Federation decider-PBT pattern. Universal claims across
generated inputs:

  - state=None always raises FacilityNotFoundError.
  - state.status=Decommissioned always raises
    FacilityCannotAddTrustAnchorCredentialError (shared lifecycle arm).
  - state.status=Active + credential absent always raises
    FacilityTrustAnchorCredentialNotPresentError.
  - state.status=Active + credential present emits exactly one
    FacilityTrustAnchorCredentialRemoved carrying the injected
    now / removed_by + reason.
  - Pure: same (state, command, now, removed_by) returns the same events.
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
    FacilityTrustAnchorCredentialNotPresentError,
)
from cora.federation.features import remove_facility_trust_anchor_credential
from cora.federation.features.remove_facility_trust_anchor_credential import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from uuid import UUID

_CODE_SITE = FacilityCode("aps-site")
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_REASON = printable_ascii_text(min_size=0, max_size=200) | st.none()


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


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_remove_facility_trust_anchor_credential_on_none_state_always_raises_not_found(
    facility_id: UUID,
    credential_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state=None -> FacilityNotFoundError, regardless of command."""
    command = RemoveFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
        reason=reason,
    )
    with pytest.raises(FacilityNotFoundError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=None,
            command=command,
            now=now,
            removed_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_remove_facility_trust_anchor_credential_on_decommissioned_always_raises_cannot(
    facility_id: UUID,
    credential_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Decommissioned -> FacilityCannotAddTrustAnchorCredentialError."""
    state = _site_facility(
        facility_id,
        actor_id,
        status=FacilityStatus.DECOMMISSIONED,
        trust_anchors=frozenset({CredentialId(credential_id)}),
    )
    command = RemoveFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
        reason=reason,
    )
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=state,
            command=command,
            now=now,
            removed_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_remove_facility_trust_anchor_credential_on_absent_raises_not_present(
    facility_id: UUID,
    credential_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """state.status=Active + absent credential -> not-present error."""
    state = _site_facility(facility_id, actor_id, status=FacilityStatus.ACTIVE)
    command = RemoveFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
        reason=reason,
    )
    with pytest.raises(FacilityTrustAnchorCredentialNotPresentError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=state,
            command=command,
            now=now,
            removed_by=ActorId(actor_id),
        )
    assert exc.value.facility_id == facility_id
    assert exc.value.credential_id == credential_id


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_remove_facility_trust_anchor_credential_on_present_emits_single_event(
    facility_id: UUID,
    credential_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Active + present credential -> single Removed event with injected fields."""
    state = _site_facility(
        facility_id,
        actor_id,
        status=FacilityStatus.ACTIVE,
        trust_anchors=frozenset({CredentialId(credential_id)}),
    )
    command = RemoveFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
        reason=reason,
    )
    events = remove_facility_trust_anchor_credential.decide(
        state=state,
        command=command,
        now=now,
        removed_by=ActorId(actor_id),
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == facility_id
    assert event.credential_id == credential_id
    assert event.removed_by == actor_id
    assert event.occurred_at == now
    assert event.reason == reason


@pytest.mark.unit
@given(
    facility_id=st.uuids(),
    credential_id=st.uuids(),
    reason=_REASON,
    now=aware_datetimes(),
    actor_id=st.uuids(),
)
def test_remove_facility_trust_anchor_credential_is_pure_same_input_same_output(
    facility_id: UUID,
    credential_id: UUID,
    reason: str | None,
    now: datetime,
    actor_id: UUID,
) -> None:
    """Two calls with identical args return identical events."""
    state = _site_facility(
        facility_id,
        actor_id,
        status=FacilityStatus.ACTIVE,
        trust_anchors=frozenset({CredentialId(credential_id)}),
    )
    command = RemoveFacilityTrustAnchorCredential(
        facility_id=FacilityId(facility_id),
        credential_id=CredentialId(credential_id),
        reason=reason,
    )
    first = remove_facility_trust_anchor_credential.decide(
        state=state, command=command, now=now, removed_by=ActorId(actor_id)
    )
    second = remove_facility_trust_anchor_credential.decide(
        state=state, command=command, now=now, removed_by=ActorId(actor_id)
    )
    assert first == second
