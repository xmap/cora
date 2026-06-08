"""Facility evolver: replay events to reconstruct state."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    Facility,
    FacilityDecommissioned,
    FacilityKind,
    FacilityName,
    FacilityRegistered,
    FacilityStatus,
    evolve,
    fold,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import AlternateIdentifier, AlternateIdentifierKind
from cora.shared.identity import ActorId

_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac1"))
_PARENT_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-00000000fac2"))
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac01"))
_REGISTERED_AT = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_DECOMMISSIONED_AT = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_CODE = FacilityCode("aps")


def _site_genesis(
    *,
    code: FacilityCode = _CODE,
    alternate_identifiers: frozenset[AlternateIdentifier] = frozenset(),
) -> FacilityRegistered:
    return FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=code,
        display_name="Advanced Photon Source",
        kind=FacilityKind.SITE,
        parent_id=None,
        registered_by=_ACTOR_ID,
        occurred_at=_REGISTERED_AT,
        alternate_identifiers=alternate_identifiers,
    )


def _area_genesis() -> FacilityRegistered:
    return FacilityRegistered(
        facility_id=_FACILITY_ID,
        code=FacilityCode("2-bm"),
        display_name="2-BM Beamline",
        kind=FacilityKind.AREA,
        parent_id=_PARENT_FACILITY_ID,
        registered_by=_ACTOR_ID,
        occurred_at=_REGISTERED_AT,
    )


# ---------- fold empty stream ----------


@pytest.mark.unit
def test_fold_empty_stream_returns_none() -> None:
    assert fold([]) is None


# ---------- genesis transitions ----------


@pytest.mark.unit
def test_fold_site_genesis_lands_active() -> None:
    state = fold([_site_genesis()])
    assert state == Facility(
        id=_FACILITY_ID,
        code=_CODE,
        display_name=FacilityName("Advanced Photon Source"),
        kind=FacilityKind.SITE,
        parent_id=None,
        trust_anchor_credential_ids=frozenset(),
        status=FacilityStatus.ACTIVE,
        persistent_id=None,
        alternate_identifiers=frozenset(),
        registered_at=_REGISTERED_AT,
        registered_by=_ACTOR_ID,
        decommissioned_at=None,
        decommissioned_by=None,
    )


@pytest.mark.unit
def test_fold_area_genesis_lands_active_with_parent() -> None:
    state = fold([_area_genesis()])
    assert state is not None
    assert state.kind is FacilityKind.AREA
    assert state.parent_id == _PARENT_FACILITY_ID
    assert state.status is FacilityStatus.ACTIVE


@pytest.mark.unit
def test_fold_genesis_folds_occurred_at_into_registered_at() -> None:
    state = fold([_site_genesis()])
    assert state is not None
    assert state.registered_at == _REGISTERED_AT
    assert state.registered_by == _ACTOR_ID


@pytest.mark.unit
def test_fold_genesis_with_alternate_identifiers_preserves_set() -> None:
    alts = frozenset({AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="aps-id-42")})
    state = fold([_site_genesis(alternate_identifiers=alts)])
    assert state is not None
    assert state.alternate_identifiers == alts


# ---------- terminal transition ----------


@pytest.mark.unit
def test_fold_genesis_then_decommission_lands_decommissioned() -> None:
    state = fold(
        [
            _site_genesis(),
            FacilityDecommissioned(
                facility_id=_FACILITY_ID,
                decommissioned_by=_ACTOR_ID,
                occurred_at=_DECOMMISSIONED_AT,
                reason="end-of-life",
            ),
        ]
    )
    assert state is not None
    assert state.status is FacilityStatus.DECOMMISSIONED
    assert state.decommissioned_at == _DECOMMISSIONED_AT
    assert state.decommissioned_by == _ACTOR_ID


@pytest.mark.unit
def test_fold_decommission_preserves_pre_terminal_fields() -> None:
    state = fold(
        [
            _site_genesis(
                alternate_identifiers=frozenset(
                    {AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="aps-id")}
                )
            ),
            FacilityDecommissioned(
                facility_id=_FACILITY_ID,
                decommissioned_by=_ACTOR_ID,
                occurred_at=_DECOMMISSIONED_AT,
            ),
        ]
    )
    assert state is not None
    assert state.code == _CODE
    assert state.kind is FacilityKind.SITE
    assert state.registered_at == _REGISTERED_AT
    assert state.alternate_identifiers == frozenset(
        {AlternateIdentifier(kind=AlternateIdentifierKind.OTHER, value="aps-id")}
    )


# ---------- transition guards via require_state ----------


@pytest.mark.unit
def test_evolve_decommission_on_none_state_raises_value_error() -> None:
    with pytest.raises(ValueError):
        evolve(
            None,
            FacilityDecommissioned(
                facility_id=_FACILITY_ID,
                decommissioned_by=_ACTOR_ID,
                occurred_at=_DECOMMISSIONED_AT,
            ),
        )
