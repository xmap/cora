"""Application-handler tests for the `decommission_facility` slice.

Pins single-stream terminal transition (FacilityDecommissioned on the
Facility stream via EventStore.append; no Decision audit cross-write
per project_facility_aggregate_design), load-decide-append behavior,
authz-deny passes UnauthorizedError without writing, and re-decommission
surfaces FacilityCannotDecommissionError.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    FacilityCannotDecommissionError,
    FacilityKind,
    FacilityNotFoundError,
    facility_stream_id,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import decommission_facility, register_facility
from cora.federation.features.decommission_facility import DecommissionFacility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTER_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed301")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed302")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed399")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed3aa")
_CODE = "aps"


async def _seed_active_facility(store: InMemoryEventStore) -> FacilityId:
    """Run register_facility to seed an Active Facility row in the store."""
    deps = _build_deps_shared(
        ids=[_REGISTER_EVENT_ID],
        now=_REGISTER_NOW,
        event_store=store,
    )
    register_handler = register_facility.bind(deps)
    facility_id = await register_handler(
        RegisterFacility(
            code=_CODE,
            display_name="Advanced Photon Source",
            kind=FacilityKind.SITE,
            parent_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return FacilityId(facility_id)


def _decommission_deps(
    *,
    event_store: InMemoryEventStore,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_DECOMMISSION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


# ---------- happy path: terminal transition appends one event ----------


@pytest.mark.unit
async def test_decommission_facility_handler_appends_decommissioned_event() -> None:
    """Active facility -> FacilityDecommissioned appended to Facility stream."""
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)

    deps = _decommission_deps(event_store=store)
    handler = decommission_facility.bind(deps)
    await handler(
        DecommissionFacility(facility_id=facility_id, reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Facility", facility_id)
    assert version == 2  # genesis + decommission
    assert len(events) == 2
    assert events[0].event_type == "FacilityRegistered"
    assert events[1].event_type == "FacilityDecommissioned"
    assert events[1].payload["decommissioned_by"] == str(_PRINCIPAL_ID)
    assert events[1].payload["reason"] == "end-of-life"
    assert events[1].payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_decommission_facility_handler_returns_none() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)
    deps = _decommission_deps(event_store=store)
    handler = decommission_facility.bind(deps)
    result = await handler(
        DecommissionFacility(facility_id=facility_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


# ---------- not-found surface ----------


@pytest.mark.unit
async def test_decommission_facility_handler_raises_not_found_on_empty_stream() -> None:
    store = InMemoryEventStore()
    deps = _decommission_deps(event_store=store)
    handler = decommission_facility.bind(deps)
    unknown_id = FacilityId(facility_stream_id(FacilityCode("unknown")))
    with pytest.raises(FacilityNotFoundError):
        await handler(
            DecommissionFacility(facility_id=unknown_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- strict-not-idempotent: second decommission raises ----------


@pytest.mark.unit
async def test_decommission_facility_handler_second_call_raises_cannot_decommission() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)

    first_deps = _decommission_deps(event_store=store)
    first_handler = decommission_facility.bind(first_deps)
    await first_handler(
        DecommissionFacility(facility_id=facility_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_deps = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000fed3bb")],
        now=_NOW,
        event_store=store,
    )
    second_handler = decommission_facility.bind(second_deps)
    with pytest.raises(FacilityCannotDecommissionError):
        await second_handler(
            DecommissionFacility(facility_id=facility_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- authz deny ----------


@pytest.mark.unit
async def test_decommission_facility_handler_denied_raises_unauthorized() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)
    deps = _decommission_deps(event_store=store, deny=True)
    handler = decommission_facility.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DecommissionFacility(facility_id=facility_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_decommission_facility_handler_denied_writes_nothing() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)
    deps = _decommission_deps(event_store=store, deny=True)
    handler = decommission_facility.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            DecommissionFacility(facility_id=facility_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Facility", facility_id)
    # Only the genesis event from _seed_active_facility; no decommission.
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "FacilityRegistered"


# ---------- no Decision audit cross-write ----------


@pytest.mark.unit
async def test_decommission_facility_handler_does_not_write_decision_stream() -> None:
    """Per design memo: decommission_facility does NOT emit Decision audit
    (Facility lifecycle is structural-scaffolding metadata, not
    authorization-decision-bearing)."""
    store = InMemoryEventStore()
    facility_id = await _seed_active_facility(store)
    deps = _decommission_deps(event_store=store)
    handler = decommission_facility.bind(deps)
    await handler(
        DecommissionFacility(facility_id=facility_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_events, decision_version = await store.load(
        "Decision", UUID("00000000-0000-0000-0000-000000000099")
    )
    assert decision_version == 0
    assert decision_events == []
