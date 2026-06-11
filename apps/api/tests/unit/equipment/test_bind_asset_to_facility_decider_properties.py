"""Property-based tests for `bind_asset_to_facility.decide` (Slice 8C).

Pins three Hypothesis-driven invariants:
  - Determinism: identical inputs yield identical outputs (no
    hidden randomness; no clock / id-gen / port reads inside the
    decider).
  - Set-once: for every facility_code currently on the Asset state,
    re-binding raises AssetFacilityCodeAlreadyAssignedError without
    consulting the lookup result.
  - Source-of-truth: when the lookup result is non-None, the
    emitted event's facility_code equals
    `facility_lookup_result.code` (NOT a command-echo).
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates.asset import (
    Asset,
    AssetFacilityCodeAlreadyAssignedError,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.equipment.features.bind_asset_to_facility import BindAssetToFacility, decide
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from tests._strategies import aware_datetimes

_TEST_ACTOR_ID = ActorId(UUID("00000000-0000-0000-0000-000000000099"))

_FACILITY_CODES = st.sampled_from(["aps", "maxiv", "esrf", "diamond", "spring8", "cora"])


def _asset(asset_id: UUID, *, facility_code: FacilityCode | None = None) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("X"),
        tier=AssetTier.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
        facility_code=facility_code,
    )


@pytest.mark.unit
@given(
    code=_FACILITY_CODES,
    now=aware_datetimes(),
    asset_id=st.uuids(),
)
def test_decide_is_pure_same_inputs_same_outputs(code: str, now: datetime, asset_id: UUID) -> None:
    """Two calls with identical args return identical events."""
    state = _asset(asset_id)
    command = BindAssetToFacility(asset_id=asset_id, facility_code=code)
    result = FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )

    first = decide(
        state=state,
        command=command,
        now=now,
        assigned_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )
    second = decide(
        state=state,
        command=command,
        now=now,
        assigned_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )
    assert first == second


@pytest.mark.unit
@given(
    current_code=_FACILITY_CODES,
    new_code=_FACILITY_CODES,
    now=aware_datetimes(),
    asset_id=st.uuids(),
)
def test_decide_rejects_rebind_for_any_pair_of_facility_codes(
    current_code: str,
    new_code: str,
    now: datetime,
    asset_id: UUID,
) -> None:
    """Set-once per Lock L2: regardless of which facility_code the
    Asset currently carries, re-binding raises."""
    state = _asset(asset_id, facility_code=FacilityCode(current_code))
    command = BindAssetToFacility(asset_id=asset_id, facility_code=new_code)
    result = FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(new_code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )

    with pytest.raises(AssetFacilityCodeAlreadyAssignedError):
        decide(
            state=state,
            command=command,
            now=now,
            assigned_by=_TEST_ACTOR_ID,
            facility_lookup_result=result,
        )


@pytest.mark.unit
@given(
    command_code=_FACILITY_CODES,
    lookup_code=_FACILITY_CODES,
    now=aware_datetimes(),
    asset_id=st.uuids(),
)
def test_decide_uses_lookup_code_not_command_code_on_emission(
    command_code: str,
    lookup_code: str,
    now: datetime,
    asset_id: UUID,
) -> None:
    """The emitted event's facility_code is the LOOKUP result's
    canonical code, not the command-echo."""
    state = _asset(asset_id)
    command = BindAssetToFacility(asset_id=asset_id, facility_code=command_code)
    result = FacilityLookupResult(
        id=uuid4(),
        code=FacilityCode(lookup_code),
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset[UUID](),
    )

    events = decide(
        state=state,
        command=command,
        now=now,
        assigned_by=_TEST_ACTOR_ID,
        facility_lookup_result=result,
    )

    assert events[0].facility_code == FacilityCode(lookup_code)
