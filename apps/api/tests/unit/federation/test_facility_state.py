"""Facility aggregate state, VO, enum, and invariant unit tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityAreaCannotHaveTrustAnchorsError,
    FacilityAreaMustHaveParentError,
    FacilityKind,
    FacilityName,
    FacilitySiteCannotHaveParentError,
    FacilityStatus,
    InvalidFacilityNameError,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac1"))
_PARENT_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac2"))
_CREDENTIAL_ID = CredentialId(UUID("01900000-0000-7000-8000-00000000ced1"))
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_CODE = FacilityCode("aps")


# ---------- FacilityName VO ----------


@pytest.mark.unit
def test_facility_name_accepts_normal_string() -> None:
    assert FacilityName("Advanced Photon Source").value == "Advanced Photon Source"


@pytest.mark.unit
def test_facility_name_trims_whitespace() -> None:
    assert FacilityName("  Advanced Photon Source  ").value == "Advanced Photon Source"


@pytest.mark.unit
def test_facility_name_empty_raises() -> None:
    with pytest.raises(InvalidFacilityNameError):
        FacilityName("")


@pytest.mark.unit
def test_facility_name_whitespace_only_raises() -> None:
    with pytest.raises(InvalidFacilityNameError):
        FacilityName("   ")


@pytest.mark.unit
def test_facility_name_over_max_length_raises() -> None:
    with pytest.raises(InvalidFacilityNameError):
        FacilityName("x" * 201)


@pytest.mark.unit
def test_facility_name_at_max_length_succeeds() -> None:
    at_limit = "x" * 200
    assert FacilityName(at_limit).value == at_limit


# ---------- FacilityKind + FacilityStatus enums ----------


@pytest.mark.unit
def test_facility_kind_values_are_pascal_case_strings() -> None:
    assert FacilityKind.SITE.value == "Site"
    assert FacilityKind.AREA.value == "Area"


@pytest.mark.unit
def test_facility_kind_is_closed_at_two_arms() -> None:
    assert set(FacilityKind) == {FacilityKind.SITE, FacilityKind.AREA}


@pytest.mark.unit
def test_facility_status_values_are_pascal_case_strings() -> None:
    assert FacilityStatus.ACTIVE.value == "Active"
    assert FacilityStatus.DECOMMISSIONED.value == "Decommissioned"


@pytest.mark.unit
def test_facility_status_is_closed_at_two_arms() -> None:
    assert set(FacilityStatus) == {FacilityStatus.ACTIVE, FacilityStatus.DECOMMISSIONED}


# ---------- Facility dataclass: structural invariants ----------


def _site(*, trust_anchors: frozenset[CredentialId] = frozenset()) -> Facility:
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
        registered_at=_NOW,
        registered_by=_ACTOR_ID,
        decommissioned_at=None,
        decommissioned_by=None,
    )


def _area(*, parent_id: FacilityId | None = _PARENT_FACILITY_ID) -> Facility:
    return Facility(
        id=_FACILITY_ID,
        code=FacilityCode("2-bm"),
        display_name=FacilityName("2-BM Beamline"),
        kind=FacilityKind.AREA,
        parent_id=parent_id,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_NOW,
        registered_by=_ACTOR_ID,
        decommissioned_at=None,
        decommissioned_by=None,
    )


@pytest.mark.unit
def test_site_facility_with_null_parent_constructs() -> None:
    site = _site()
    assert site.kind is FacilityKind.SITE
    assert site.parent_id is None


@pytest.mark.unit
def test_site_facility_with_non_null_parent_raises() -> None:
    with pytest.raises(FacilitySiteCannotHaveParentError) as excinfo:
        Facility(
            id=_FACILITY_ID,
            code=_CODE,
            display_name=FacilityName("Advanced Photon Source"),
            kind=FacilityKind.SITE,
            parent_id=_PARENT_FACILITY_ID,
            trust_anchor_credential_ids=frozenset(),
            status=FacilityStatus.ACTIVE,
            persistent_id=None,
            alternate_identifiers=frozenset(),
            registered_at=_NOW,
            registered_by=_ACTOR_ID,
            decommissioned_at=None,
            decommissioned_by=None,
        )
    assert excinfo.value.code == _CODE
    assert excinfo.value.parent_id == _PARENT_FACILITY_ID


@pytest.mark.unit
def test_area_facility_with_parent_constructs() -> None:
    area = _area()
    assert area.kind is FacilityKind.AREA
    assert area.parent_id == _PARENT_FACILITY_ID


@pytest.mark.unit
def test_area_facility_with_null_parent_raises() -> None:
    with pytest.raises(FacilityAreaMustHaveParentError) as excinfo:
        _area(parent_id=None)
    assert excinfo.value.code == FacilityCode("2-bm")


@pytest.mark.unit
def test_area_facility_with_trust_anchors_raises() -> None:
    with pytest.raises(FacilityAreaCannotHaveTrustAnchorsError) as excinfo:
        Facility(
            id=_FACILITY_ID,
            code=FacilityCode("2-bm"),
            display_name=FacilityName("2-BM Beamline"),
            kind=FacilityKind.AREA,
            parent_id=_PARENT_FACILITY_ID,
            trust_anchor_credential_ids=frozenset({_CREDENTIAL_ID}),
            status=FacilityStatus.ACTIVE,
            persistent_id=None,
            alternate_identifiers=frozenset(),
            registered_at=_NOW,
            registered_by=_ACTOR_ID,
            decommissioned_at=None,
            decommissioned_by=None,
        )
    assert excinfo.value.code == FacilityCode("2-bm")


@pytest.mark.unit
def test_site_facility_accepts_trust_anchors() -> None:
    site = _site(trust_anchors=frozenset({_CREDENTIAL_ID}))
    assert site.trust_anchor_credential_ids == frozenset({_CREDENTIAL_ID})
