"""Unit tests for the `remove_facility_trust_anchor_credential` slice's pure decider.

Pin the not-found guard, the shared lifecycle guard (Decommissioned
raises FacilityCannotAddTrustAnchorCredentialError; kind=Area is
structurally impossible to have non-empty trust anchors so no separate
guard fires there), the strict-not-idempotent not-present guard, the
valid Active+Site transition, reason carriage, purity, and handler-
injected removed_by / now capture.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

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

_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000facc01"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000facc02"))
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000facc03"))
_CREDENTIAL_ID = CredentialId(UUID("01900000-0000-7000-8000-000000facc04"))
_CODE = FacilityCode("aps")


def _command(**overrides: object) -> RemoveFacilityTrustAnchorCredential:
    base: dict[str, object] = {
        "facility_id": _FACILITY_ID,
        "credential_id": _CREDENTIAL_ID,
        "reason": "key compromise",
    }
    base.update(overrides)
    return RemoveFacilityTrustAnchorCredential(**base)  # type: ignore[arg-type]


def _active_site_facility(
    *, trust_anchors: frozenset[CredentialId] = frozenset({_CREDENTIAL_ID})
) -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=trust_anchors,
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


def _decommissioned_site_facility() -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset({_CREDENTIAL_ID}),
        status=FacilityStatus.DECOMMISSIONED,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )


# ---------- not-found guard ----------


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_rejects_none_state_as_not_found() -> None:
    with pytest.raises(FacilityNotFoundError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=None,
            command=_command(),
            now=_NOW,
            removed_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID


# ---------- shared lifecycle guard ----------


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_rejects_decommissioned_facility() -> None:
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=_decommissioned_site_facility(),
            command=_command(),
            now=_NOW,
            removed_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _CREDENTIAL_ID


# ---------- strict-not-idempotent not-present guard ----------


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_rejects_absent_credential() -> None:
    state = _active_site_facility(trust_anchors=frozenset())
    with pytest.raises(FacilityTrustAnchorCredentialNotPresentError) as exc:
        remove_facility_trust_anchor_credential.decide(
            state=state,
            command=_command(),
            now=_NOW,
            removed_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _CREDENTIAL_ID


# ---------- valid transition ----------


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_emits_one_event_for_present_credential() -> None:
    events = remove_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=_NOW,
        removed_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == _FACILITY_ID
    assert event.credential_id == _CREDENTIAL_ID
    assert event.removed_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW
    assert event.reason == "key compromise"


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_accepts_none_reason() -> None:
    events = remove_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(reason=None),
        now=_NOW,
        removed_by=_PRINCIPAL_ID,
    )
    assert events[0].reason is None


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_is_pure_same_inputs_same_outputs() -> None:
    state = _active_site_facility()
    first = remove_facility_trust_anchor_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        removed_by=_PRINCIPAL_ID,
    )
    second = remove_facility_trust_anchor_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        removed_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_uses_handler_injected_actor_verbatim() -> None:
    injected = ActorId(uuid4())
    events = remove_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=_NOW,
        removed_by=injected,
    )
    assert events[0].removed_by == injected


@pytest.mark.unit
def test_remove_facility_trust_anchor_credential_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2030, 12, 31, 23, 59, 59, tzinfo=UTC)
    events = remove_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=custom_now,
        removed_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
