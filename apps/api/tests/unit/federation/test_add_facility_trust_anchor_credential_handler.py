"""Application-handler tests for the `add_facility_trust_anchor_credential` slice.

Pins single-stream transition (FacilityTrustAnchorCredentialAdded on the
Facility stream via EventStore.append; no Decision audit cross-write
per [[project_slice6_design]]), load-decide-append behavior,
authz-deny passes UnauthorizedError without writing, strict-not-idempotent
replay surfaces FacilityTrustAnchorCredentialAlreadyPresentError, and
lifecycle/kind guards surface FacilityCannotAddTrustAnchorCredentialError.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.facility import (
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityKind,
    FacilityNotFoundError,
    FacilityTrustAnchorCredentialAlreadyPresentError,
    facility_stream_id,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import (
    add_facility_trust_anchor_credential,
    decommission_facility,
    register_facility,
)
from cora.federation.features.add_facility_trust_anchor_credential import (
    AddFacilityTrustAnchorCredential,
)
from cora.federation.features.decommission_facility import DecommissionFacility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared

_REGISTER_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000facb11")
_AREA_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000facb12")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000facb13")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000facb14")
_ADD_EVENT_ID_2 = UUID("01900000-0000-7000-8000-000000facb15")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000facb99")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000facbaa")
_CREDENTIAL_ID = CredentialId(UUID("01900000-0000-7000-8000-000000facb44"))
_SITE_CODE = "aps"
_AREA_CODE = "aps-2-bm"


async def _seed_active_site_facility(store: InMemoryEventStore) -> FacilityId:
    """Run register_facility to seed an Active Site Facility row in the store."""
    deps = _build_deps_shared(
        ids=[_REGISTER_EVENT_ID],
        now=_REGISTER_NOW,
        event_store=store,
    )
    register_handler = register_facility.bind(deps)
    facility_id = await register_handler(
        RegisterFacility(
            code=_SITE_CODE,
            display_name="Advanced Photon Source",
            kind=FacilityKind.SITE,
            parent_id=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return FacilityId(facility_id)


async def _seed_active_area_facility(
    store: InMemoryEventStore,
    parent_id: FacilityId,
) -> FacilityId:
    """Run register_facility (with a Site parent) to seed an Active Area Facility row."""
    parent_lookup = InMemoryFacilityLookup()
    parent_lookup.register(
        facility_id=parent_id,
        code=_SITE_CODE,
        kind="Site",
    )
    deps = _build_deps_shared(
        ids=[_AREA_REGISTER_EVENT_ID],
        now=_REGISTER_NOW,
        event_store=store,
        facility_lookup=parent_lookup,
    )
    register_handler = register_facility.bind(deps)
    facility_id = await register_handler(
        RegisterFacility(
            code=_AREA_CODE,
            display_name="APS 2-BM Beamline",
            kind=FacilityKind.AREA,
            parent_id=parent_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return FacilityId(facility_id)


def _add_deps(
    *,
    event_store: InMemoryEventStore,
    ids: list[UUID] | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=ids or [_ADD_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


# ---------- happy path ----------


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_appends_added_event() -> None:
    """Active Site facility -> FacilityTrustAnchorCredentialAdded appended to stream."""
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)

    deps = _add_deps(event_store=store)
    handler = add_facility_trust_anchor_credential.bind(deps)
    await handler(
        AddFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Facility", facility_id)
    assert version == 2
    assert len(events) == 2
    assert events[0].event_type == "FacilityRegistered"
    assert events[1].event_type == "FacilityTrustAnchorCredentialAdded"
    assert events[1].payload["facility_id"] == str(facility_id)
    assert events[1].payload["credential_id"] == str(_CREDENTIAL_ID)
    assert events[1].payload["added_by"] == str(_PRINCIPAL_ID)
    assert events[1].payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_returns_none() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)
    deps = _add_deps(event_store=store)
    handler = add_facility_trust_anchor_credential.bind(deps)
    result = await handler(
        AddFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


# ---------- not-found surface ----------


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_raises_not_found_on_empty_stream() -> (
    None
):
    store = InMemoryEventStore()
    deps = _add_deps(event_store=store)
    handler = add_facility_trust_anchor_credential.bind(deps)
    unknown_id = FacilityId(facility_stream_id(FacilityCode("unknown")))
    with pytest.raises(FacilityNotFoundError):
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=unknown_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- strict-not-idempotent replay ----------


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_replay_raises_already_present() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)

    first_deps = _add_deps(event_store=store, ids=[_ADD_EVENT_ID])
    first_handler = add_facility_trust_anchor_credential.bind(first_deps)
    await first_handler(
        AddFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_deps = _add_deps(event_store=store, ids=[_ADD_EVENT_ID_2])
    second_handler = add_facility_trust_anchor_credential.bind(second_deps)
    with pytest.raises(FacilityTrustAnchorCredentialAlreadyPresentError):
        await second_handler(
            AddFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- lifecycle / kind guard ----------


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_decommissioned_raises_cannot() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)
    decommission_handler = decommission_facility.bind(
        _build_deps_shared(
            ids=[_DECOMMISSION_EVENT_ID],
            now=_REGISTER_NOW,
            event_store=store,
        )
    )
    await decommission_handler(
        DecommissionFacility(facility_id=facility_id, reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deps = _add_deps(event_store=store)
    handler = add_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError):
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_area_raises_cannot() -> None:
    store = InMemoryEventStore()
    site_id = await _seed_active_site_facility(store)
    area_id = await _seed_active_area_facility(store, parent_id=site_id)

    deps = _add_deps(event_store=store)
    handler = add_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError):
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=area_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- authz deny ----------


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_denied_raises_unauthorized() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)
    deps = _add_deps(event_store=store, deny=True)
    handler = add_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_add_facility_trust_anchor_credential_handler_denied_writes_nothing() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_active_site_facility(store)
    deps = _add_deps(event_store=store, deny=True)
    handler = add_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            AddFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Facility", facility_id)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "FacilityRegistered"
