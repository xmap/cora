"""Property-based tests for `register_supply.decide` (Supply BC).

Complements the example-based `test_register_supply_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, now, new_id, triggered_by,
     facility_lookup_result, asset_lookup_result) -> list[SupplyRegistered]

with two cross-BC lookups resolved at the handler edge. The
load-bearing properties:

  - Any non-None state always raises `SupplyAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - `facility_lookup_result=None` always raises
    `SupplyFacilityNotFoundError` carrying the wire-level slug.
  - A non-None `command.containing_asset_id` with
    `asset_lookup_result=None` always raises
    `SupplyContainingAssetNotFoundError` carrying the wire-level id.
  - On the happy path the single `SupplyRegistered` carries the
    INJECTED ids: supply_id=new_id, facility_code=lookup.code (not the
    command echo), containing_asset_id=asset_lookup.id (or None for the
    facility-scope path), trigger="Operator", triggered_by, occurred_at.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.ports.asset_lookup import AssetLookupResult
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId
from cora.supply.aggregates.supply import (
    Supply,
    SupplyAlreadyExistsError,
    SupplyContainingAssetNotFoundError,
    SupplyFacilityNotFoundError,
    SupplyName,
    SupplyRegistered,
    SupplyStatus,
)
from cora.supply.features import register_supply
from cora.supply.features.register_supply import RegisterSupply
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime

# The facility-lookup row id is never asserted (the canonical wire value
# is its FacilityCode, not this UUID), so a fixed constant keeps the
# helper deterministic instead of minting a fresh uuid4 per call.
_FACILITY_LOOKUP_ID = UUID("01900000-0000-7000-8000-000000000fac")

_KIND = printable_ascii_text(min_size=1, max_size=50)
_NAME = printable_ascii_text(min_size=1, max_size=200)
_REASON = printable_ascii_text(min_size=1, max_size=500)
_STATUS = st.sampled_from(list(SupplyStatus))
_FACILITY_CODES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=16)


def _facility_lookup_result(code: FacilityCode) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=_FACILITY_LOOKUP_ID,
        code=code,
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset(),
    )


def _asset_lookup_result(asset_id: UUID) -> AssetLookupResult:
    return AssetLookupResult(
        id=asset_id,
        name="2-BM",
        tier="Unit",
        lifecycle="Active",
        family_affordances=frozenset[str](),
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=_STATUS,
    kind=_KIND,
    name=_NAME,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: SupplyStatus,
    kind: str,
    name: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """Any non-None state raises SupplyAlreadyExistsError carrying state.id."""
    existing = Supply(
        id=existing_id,
        kind=kind,
        name=SupplyName(name),
        facility_code=FacilityCode(facility_code),
        status=existing_status,
    )
    with pytest.raises(SupplyAlreadyExistsError) as exc:
        register_supply.decide(
            state=existing,
            command=RegisterSupply(kind=kind, name=name, facility_code=facility_code),
            now=now,
            new_id=new_id,
            triggered_by=ActorId(triggered_by_uuid),
            facility_lookup_result=_facility_lookup_result(FacilityCode(facility_code)),
            asset_lookup_result=None,
        )
    assert exc.value.supply_id == existing_id


@pytest.mark.unit
@given(
    kind=_KIND,
    name=_NAME,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_with_missing_facility_always_raises_not_found(
    kind: str,
    name: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """facility_lookup_result=None raises SupplyFacilityNotFoundError with the slug."""
    with pytest.raises(SupplyFacilityNotFoundError) as exc:
        register_supply.decide(
            state=None,
            command=RegisterSupply(kind=kind, name=name, facility_code=facility_code),
            now=now,
            new_id=new_id,
            triggered_by=ActorId(triggered_by_uuid),
            facility_lookup_result=None,
            asset_lookup_result=None,
        )
    assert exc.value.facility_code == facility_code


@pytest.mark.unit
@given(
    kind=_KIND,
    name=_NAME,
    facility_code=_FACILITY_CODES,
    containing_asset_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_bound_asset_missing_always_raises_not_found(
    kind: str,
    name: str,
    facility_code: str,
    containing_asset_id: UUID,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """Non-None containing_asset_id + asset_lookup_result=None raises, carrying the id."""
    with pytest.raises(SupplyContainingAssetNotFoundError) as exc:
        register_supply.decide(
            state=None,
            command=RegisterSupply(
                kind=kind,
                name=name,
                facility_code=facility_code,
                containing_asset_id=containing_asset_id,
            ),
            now=now,
            new_id=new_id,
            triggered_by=ActorId(triggered_by_uuid),
            facility_lookup_result=_facility_lookup_result(FacilityCode(facility_code)),
            asset_lookup_result=None,
        )
    assert exc.value.containing_asset_id == containing_asset_id


@pytest.mark.unit
@given(
    kind=_KIND,
    name=_NAME,
    command_code=_FACILITY_CODES,
    canonical_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_facility_scope_emits_event_with_injected_fields(
    kind: str,
    name: str,
    command_code: str,
    canonical_code: str,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """Facility-scope happy path emits one event with new_id, lookup.code, no asset."""
    triggered_by = ActorId(triggered_by_uuid)
    canonical = FacilityCode(canonical_code)
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(kind=kind, name=name, facility_code=command_code),
        now=now,
        new_id=new_id,
        triggered_by=triggered_by,
        facility_lookup_result=_facility_lookup_result(canonical),
        asset_lookup_result=None,
    )
    assert events == [
        SupplyRegistered(
            supply_id=new_id,
            kind=kind,
            name=name,
            facility_code=canonical,
            trigger="Operator",
            triggered_by=triggered_by,
            occurred_at=now,
            containing_asset_id=None,
        )
    ]


@pytest.mark.unit
@given(
    kind=_KIND,
    name=_NAME,
    facility_code=_FACILITY_CODES,
    command_asset_id=st.uuids(),
    canonical_asset_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_bound_scope_uses_lookup_ids_not_command_echo(
    kind: str,
    name: str,
    facility_code: str,
    command_asset_id: UUID,
    canonical_asset_id: UUID,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """Bound happy path threads asset_lookup.id onto the event, not the command echo."""
    events = register_supply.decide(
        state=None,
        command=RegisterSupply(
            kind=kind,
            name=name,
            facility_code=facility_code,
            containing_asset_id=command_asset_id,
        ),
        now=now,
        new_id=new_id,
        triggered_by=ActorId(triggered_by_uuid),
        facility_lookup_result=_facility_lookup_result(FacilityCode(facility_code)),
        asset_lookup_result=_asset_lookup_result(canonical_asset_id),
    )
    assert events[0].containing_asset_id == canonical_asset_id


@pytest.mark.unit
@given(
    kind=_KIND,
    name=_NAME,
    facility_code=_FACILITY_CODES,
    now=aware_datetimes(),
    new_id=st.uuids(),
    triggered_by_uuid=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    kind: str,
    name: str,
    facility_code: str,
    now: datetime,
    new_id: UUID,
    triggered_by_uuid: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = RegisterSupply(kind=kind, name=name, facility_code=facility_code)
    lookup = _facility_lookup_result(FacilityCode(facility_code))
    triggered_by = ActorId(triggered_by_uuid)
    first = register_supply.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        triggered_by=triggered_by,
        facility_lookup_result=lookup,
        asset_lookup_result=None,
    )
    second = register_supply.decide(
        state=None,
        command=command,
        now=now,
        new_id=new_id,
        triggered_by=triggered_by,
        facility_lookup_result=lookup,
        asset_lookup_result=None,
    )
    assert first == second
