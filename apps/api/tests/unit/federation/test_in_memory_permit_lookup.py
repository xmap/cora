"""Unit tests for InMemoryPermitLookup."""

from uuid import uuid4

import pytest

from cora.federation.adapters.in_memory_permit_lookup import InMemoryPermitLookup
from cora.infrastructure.ports.federation import PermitLookup, PermitLookupResult
from cora.shared.facility_code import FacilityCode

_APS = FacilityCode("aps-2bm")
_NSLS = FacilityCode("nsls-ii")


def test_in_memory_permit_lookup_satisfies_permit_lookup_protocol() -> None:
    assert isinstance(InMemoryPermitLookup(), PermitLookup)


@pytest.mark.asyncio
async def test_lookup_outbound_returns_none_when_no_permit_registered() -> None:
    lookup = InMemoryPermitLookup()
    result = await lookup.lookup_outbound(_APS, "CalibrationRevision")
    assert result is None


@pytest.mark.asyncio
async def test_lookup_inbound_returns_none_when_no_permit_registered() -> None:
    lookup = InMemoryPermitLookup()
    result = await lookup.lookup_inbound(_APS, "CalibrationRevision")
    assert result is None


@pytest.mark.asyncio
async def test_register_outbound_then_lookup_outbound_returns_seeded_result() -> None:
    lookup = InMemoryPermitLookup()
    permit_id = uuid4()
    seeded = lookup.register_outbound(
        peer_facility_id=_APS,
        artifact_kind="CalibrationRevision",
        permit_id=permit_id,
    )
    result = await lookup.lookup_outbound(_APS, "CalibrationRevision")
    assert result == seeded
    assert result is not None
    assert result.permit_id == permit_id
    assert result.direction == "Outbound"
    assert result.status == "Active"
    assert result.abi_tier_floor == "Stable"


@pytest.mark.asyncio
async def test_register_inbound_then_lookup_inbound_returns_seeded_result() -> None:
    lookup = InMemoryPermitLookup()
    permit_id = uuid4()
    seeded = lookup.register_inbound(
        peer_facility_id=_NSLS, artifact_kind="Method", permit_id=permit_id
    )
    result = await lookup.lookup_inbound(_NSLS, "Method")
    assert result == seeded
    assert result is not None
    assert result.direction == "Inbound"


@pytest.mark.asyncio
async def test_outbound_and_inbound_lookups_are_keyed_independently() -> None:
    lookup = InMemoryPermitLookup()
    lookup.register_outbound(peer_facility_id=_APS, artifact_kind="Method", permit_id=uuid4())
    assert await lookup.lookup_outbound(_APS, "Method") is not None
    assert await lookup.lookup_inbound(_APS, "Method") is None


@pytest.mark.asyncio
async def test_lookup_with_different_artifact_kind_returns_none() -> None:
    lookup = InMemoryPermitLookup()
    lookup.register_outbound(
        peer_facility_id=_APS,
        artifact_kind="CalibrationRevision",
        permit_id=uuid4(),
    )
    assert await lookup.lookup_outbound(_APS, "Method") is None


@pytest.mark.asyncio
async def test_register_with_custom_status_and_floor_propagates_to_result() -> None:
    lookup = InMemoryPermitLookup()
    seeded = lookup.register_outbound(
        peer_facility_id=_APS,
        artifact_kind="CalibrationRevision",
        permit_id=uuid4(),
        status="Suspended",
        abi_tier_floor="Obsolete",
        current_version=7,
    )
    result = await lookup.lookup_outbound(_APS, "CalibrationRevision")
    assert result == seeded
    assert result is not None
    assert result.status == "Suspended"
    assert result.abi_tier_floor == "Obsolete"
    assert result.current_version == 7


@pytest.mark.asyncio
async def test_register_accepts_bare_string_peer_facility_id_for_back_compat() -> None:
    """register_outbound coerces a bare string into a FacilityCode at the
    boundary so existing test call sites that pass strings keep working
    unchanged post Slice 3 of project_structural_scope_design."""
    lookup = InMemoryPermitLookup()
    lookup.register_outbound(
        peer_facility_id="aps-2bm",
        artifact_kind="CalibrationRevision",
        permit_id=uuid4(),
    )
    result = await lookup.lookup_outbound(_APS, "CalibrationRevision")
    assert result is not None
    assert result.peer_facility_id == _APS


@pytest.mark.asyncio
async def test_clear_removes_all_registered_permits() -> None:
    lookup = InMemoryPermitLookup()
    lookup.register_outbound(
        peer_facility_id=_APS,
        artifact_kind="CalibrationRevision",
        permit_id=uuid4(),
    )
    lookup.register_inbound(peer_facility_id=_NSLS, artifact_kind="Method", permit_id=uuid4())
    lookup.clear()
    assert await lookup.lookup_outbound(_APS, "CalibrationRevision") is None
    assert await lookup.lookup_inbound(_NSLS, "Method") is None


def test_permit_lookup_result_is_frozen_dataclass_carrying_locked_fields() -> None:
    r = PermitLookupResult(
        permit_id=uuid4(),
        peer_facility_id=_APS,
        direction="Outbound",
        status="Active",
        abi_tier_floor="Stable",
        current_version=3,
    )
    assert r.peer_facility_id == _APS
    with pytest.raises(AttributeError):
        r.status = "Revoked"  # type: ignore[misc]
