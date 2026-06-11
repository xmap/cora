"""Unit tests for the `bind_asset_to_facility` slice's pure decider.

Pins the Slice 8C set-once invariant and the cross-BC binding
handshake (handler-loads + decider-rejects mirror of Slice 8A
register_asset). The decider is a pure function over
`(state, command, now, assigned_by, facility_lookup_result)`.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetFacilityCodeAlreadyAssignedError,
    AssetFacilityCodeAssigned,
    AssetFacilityNotFoundError,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.features.bind_asset_to_facility import BindAssetToFacility, decide
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))


def _asset(
    asset_id: UUID,
    *,
    facility_code: FacilityCode | None = None,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("Sample beamline"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
        facility_code=facility_code,
    )


def _lookup_result(code: str) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )


@pytest.mark.unit
def test_decide_emits_assigned_event_on_happy_path() -> None:
    asset_id = uuid4()
    state = _asset(asset_id)
    command = BindAssetToFacility(asset_id=asset_id, facility_code="aps")
    result = _lookup_result("aps")

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        assigned_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )

    assert events == [
        AssetFacilityCodeAssigned(
            asset_id=asset_id,
            facility_code=FacilityCode("aps"),
            occurred_at=_NOW,
            assigned_by=_TEST_ACTOR_ID,
        )
    ]


@pytest.mark.unit
def test_decide_uses_lookup_result_code_not_command_echo() -> None:
    """Source-of-truth: the projection's canonical FacilityCode wins
    over whatever the operator typed (case normalization happens at
    the FacilityLookup adapter)."""
    asset_id = uuid4()
    state = _asset(asset_id)
    command = BindAssetToFacility(asset_id=asset_id, facility_code="aps")
    # Lookup result returns a different code (canonicalized).
    result = _lookup_result("aps-main")

    events = decide(
        state=state,
        command=command,
        now=_NOW,
        assigned_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )

    assert events[0].facility_code == FacilityCode("aps-main")


@pytest.mark.unit
def test_decide_rejects_when_asset_does_not_exist() -> None:
    asset_id = uuid4()
    command = BindAssetToFacility(asset_id=asset_id, facility_code="aps")
    with pytest.raises(AssetNotFoundError) as exc_info:
        decide(
            state=None,
            command=command,
            now=_NOW,
            assigned_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("aps"),
        )
    assert exc_info.value.asset_id == asset_id


@pytest.mark.unit
def test_decide_rejects_when_asset_already_has_facility_code() -> None:
    """Set-once per Lock L2: re-binding raises
    AssetFacilityCodeAlreadyAssignedError carrying both the asset id
    and the current FacilityCode for operator diagnostic."""
    asset_id = uuid4()
    state = _asset(asset_id, facility_code=FacilityCode("aps"))
    command = BindAssetToFacility(asset_id=asset_id, facility_code="maxiv")
    with pytest.raises(AssetFacilityCodeAlreadyAssignedError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            assigned_by=_TEST_ACTOR_ID,
            facility_lookup_result=_lookup_result("maxiv"),
        )
    assert exc_info.value.asset_id == asset_id
    assert exc_info.value.current_facility_code == FacilityCode("aps")


@pytest.mark.unit
def test_decide_rejects_when_facility_code_does_not_resolve() -> None:
    asset_id = uuid4()
    state = _asset(asset_id)
    command = BindAssetToFacility(asset_id=asset_id, facility_code="ghost")
    with pytest.raises(AssetFacilityNotFoundError) as exc_info:
        decide(
            state=state,
            command=command,
            now=_NOW,
            assigned_by=_TEST_ACTOR_ID,
            facility_lookup_result=None,
        )
    assert exc_info.value.facility_code == "ghost"
