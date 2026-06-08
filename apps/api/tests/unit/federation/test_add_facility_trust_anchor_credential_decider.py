"""Unit tests for the `add_facility_trust_anchor_credential` slice's pure decider.

Pin the not-found guard, the shared lifecycle/kind guard
(Decommissioned + kind=Area both raise FacilityCannotAddTrustAnchorCredentialError),
the strict-not-idempotent already-present guard, the valid Active+Site
transition, purity, and handler-injected added_by / now capture.
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
    FacilityTrustAnchorCredentialAlreadyPresentError,
)
from cora.federation.features import add_facility_trust_anchor_credential
from cora.federation.features.add_facility_trust_anchor_credential import (
    AddFacilityTrustAnchorCredential,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000facb01"))
_PRINCIPAL_ID = ActorId(UUID("01900000-0000-7000-8000-000000facb02"))
_REGISTERED_BY = ActorId(UUID("01900000-0000-7000-8000-000000facb03"))
_CREDENTIAL_ID = CredentialId(UUID("01900000-0000-7000-8000-000000facb04"))
_PARENT_ID = FacilityId(UUID("01900000-0000-7000-8000-000000facb05"))
_CODE_SITE = FacilityCode("aps")
_CODE_AREA = FacilityCode("aps-2-bm")


def _command(**overrides: object) -> AddFacilityTrustAnchorCredential:
    base: dict[str, object] = {
        "facility_id": _FACILITY_ID,
        "credential_id": _CREDENTIAL_ID,
    }
    base.update(overrides)
    return AddFacilityTrustAnchorCredential(**base)  # type: ignore[arg-type]


def _active_site_facility(*, trust_anchors: frozenset[CredentialId] = frozenset()) -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE_SITE,
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
        code=_CODE_SITE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.DECOMMISSIONED,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=_NOW,
        decommissioned_by=_PRINCIPAL_ID,
    )


def _active_area_facility() -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=_CODE_AREA,
        display_name=FacilityName("APS 2-BM Beamline"),
        kind=FacilityKind.AREA,
        parent_id=_PARENT_ID,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_REGISTERED_BY,
        decommissioned_at=None,
        decommissioned_by=None,
    )


# ---------- not-found guard ----------


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_rejects_none_state_as_not_found() -> None:
    with pytest.raises(FacilityNotFoundError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=None,
            command=_command(),
            now=_NOW,
            added_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID


# ---------- shared lifecycle/kind guard ----------


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_rejects_decommissioned_facility() -> None:
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=_decommissioned_site_facility(),
            command=_command(),
            now=_NOW,
            added_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _CREDENTIAL_ID
    assert "decommissioned" in exc.value.reason.lower()


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_rejects_area_kind() -> None:
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=_active_area_facility(),
            command=_command(),
            now=_NOW,
            added_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _CREDENTIAL_ID
    assert "area" in exc.value.reason.lower()


# ---------- strict-not-idempotent already-present guard ----------


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_rejects_already_present_credential() -> None:
    state = _active_site_facility(trust_anchors=frozenset({_CREDENTIAL_ID}))
    with pytest.raises(FacilityTrustAnchorCredentialAlreadyPresentError) as exc:
        add_facility_trust_anchor_credential.decide(
            state=state,
            command=_command(),
            now=_NOW,
            added_by=_PRINCIPAL_ID,
        )
    assert exc.value.facility_id == _FACILITY_ID
    assert exc.value.credential_id == _CREDENTIAL_ID


# ---------- valid transition ----------


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_emits_one_event_for_active_site() -> None:
    events = add_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=_NOW,
        added_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    event = events[0]
    assert event.facility_id == _FACILITY_ID
    assert event.credential_id == _CREDENTIAL_ID
    assert event.added_by == _PRINCIPAL_ID
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_admits_second_distinct_credential() -> None:
    other_credential = CredentialId(uuid4())
    state = _active_site_facility(trust_anchors=frozenset({other_credential}))
    events = add_facility_trust_anchor_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        added_by=_PRINCIPAL_ID,
    )
    assert len(events) == 1
    assert events[0].credential_id == _CREDENTIAL_ID


# ---------- purity + handler-injected capture ----------


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_is_pure_same_inputs_same_outputs() -> None:
    state = _active_site_facility()
    first = add_facility_trust_anchor_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        added_by=_PRINCIPAL_ID,
    )
    second = add_facility_trust_anchor_credential.decide(
        state=state,
        command=_command(),
        now=_NOW,
        added_by=_PRINCIPAL_ID,
    )
    assert first == second


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_uses_handler_injected_actor_verbatim() -> None:
    injected = ActorId(uuid4())
    events = add_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=_NOW,
        added_by=injected,
    )
    assert events[0].added_by == injected


@pytest.mark.unit
def test_add_facility_trust_anchor_credential_uses_handler_injected_now_verbatim() -> None:
    custom_now = datetime(2030, 12, 31, 23, 59, 59, tzinfo=UTC)
    events = add_facility_trust_anchor_credential.decide(
        state=_active_site_facility(),
        command=_command(),
        now=custom_now,
        added_by=_PRINCIPAL_ID,
    )
    assert events[0].occurred_at == custom_now
