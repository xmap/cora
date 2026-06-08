"""Application-handler tests for the `remove_facility_trust_anchor_credential` slice.

Pins single-stream transition (FacilityTrustAnchorCredentialRemoved on
the Facility stream via EventStore.append; no Decision audit cross-write
per [[project_slice6_design]]), load-decide-append behavior, authz-deny
passes UnauthorizedError without writing, strict-not-idempotent replay
surfaces FacilityTrustAnchorCredentialNotPresentError, and Decommissioned
state surfaces FacilityCannotAddTrustAnchorCredentialError.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import CredentialId, FacilityId
from cora.federation.aggregates.facility import (
    FacilityCannotAddTrustAnchorCredentialError,
    FacilityKind,
    FacilityNotFoundError,
    FacilityTrustAnchorCredentialNotPresentError,
    facility_stream_id,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import (
    add_facility_trust_anchor_credential,
    decommission_facility,
    register_facility,
    remove_facility_trust_anchor_credential,
)
from cora.federation.features.add_facility_trust_anchor_credential import (
    AddFacilityTrustAnchorCredential,
)
from cora.federation.features.decommission_facility import DecommissionFacility
from cora.federation.features.register_facility import RegisterFacility
from cora.federation.features.remove_facility_trust_anchor_credential import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared

_REGISTER_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_ADD_NOW = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
_NOW = datetime(2026, 7, 1, 9, 30, 0, tzinfo=UTC)
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-000000facd11")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000facd12")
_DECOMMISSION_EVENT_ID = UUID("01900000-0000-7000-8000-000000facd13")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000facd14")
_REMOVE_EVENT_ID_2 = UUID("01900000-0000-7000-8000-000000facd15")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000facd99")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000facdaa")
_CREDENTIAL_ID = CredentialId(UUID("01900000-0000-7000-8000-000000facd44"))
_SITE_CODE = "aps"


async def _seed_site_facility_with_trust_anchor(
    store: InMemoryEventStore,
) -> FacilityId:
    """Seed an Active Site Facility with one trust-anchor credential added."""
    deps = _build_deps_shared(
        ids=[_REGISTER_EVENT_ID],
        now=_REGISTER_NOW,
        event_store=store,
    )
    register_handler = register_facility.bind(deps)
    facility_id = FacilityId(
        await register_handler(
            RegisterFacility(
                code=_SITE_CODE,
                display_name="Advanced Photon Source",
                kind=FacilityKind.SITE,
                parent_id=None,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    )

    add_deps = _build_deps_shared(
        ids=[_ADD_EVENT_ID],
        now=_ADD_NOW,
        event_store=store,
    )
    add_handler = add_facility_trust_anchor_credential.bind(add_deps)
    await add_handler(
        AddFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return facility_id


def _remove_deps(
    *,
    event_store: InMemoryEventStore,
    ids: list[UUID] | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=ids or [_REMOVE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


# ---------- happy path ----------


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_appends_removed_event() -> None:
    """Active Site facility with credential -> Removed event appended to stream."""
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)

    deps = _remove_deps(event_store=store)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    await handler(
        RemoveFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
            reason="key compromise",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Facility", facility_id)
    assert version == 3
    assert len(events) == 3
    assert events[0].event_type == "FacilityRegistered"
    assert events[1].event_type == "FacilityTrustAnchorCredentialAdded"
    assert events[2].event_type == "FacilityTrustAnchorCredentialRemoved"
    assert events[2].payload["facility_id"] == str(facility_id)
    assert events[2].payload["credential_id"] == str(_CREDENTIAL_ID)
    assert events[2].payload["removed_by"] == str(_PRINCIPAL_ID)
    assert events[2].payload["occurred_at"] == _NOW.isoformat()
    assert events[2].payload["reason"] == "key compromise"


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_returns_none() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)
    deps = _remove_deps(event_store=store)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    result = await handler(
        RemoveFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


# ---------- not-found surface ----------


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_not_found_on_empty_stream() -> None:
    store = InMemoryEventStore()
    deps = _remove_deps(event_store=store)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    unknown_id = FacilityId(facility_stream_id(FacilityCode("unknown")))
    with pytest.raises(FacilityNotFoundError):
        await handler(
            RemoveFacilityTrustAnchorCredential(
                facility_id=unknown_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- strict-not-idempotent replay ----------


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_replay_raises_not_present() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)

    first_deps = _remove_deps(event_store=store, ids=[_REMOVE_EVENT_ID])
    first_handler = remove_facility_trust_anchor_credential.bind(first_deps)
    await first_handler(
        RemoveFacilityTrustAnchorCredential(
            facility_id=facility_id,
            credential_id=_CREDENTIAL_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    second_deps = _remove_deps(event_store=store, ids=[_REMOVE_EVENT_ID_2])
    second_handler = remove_facility_trust_anchor_credential.bind(second_deps)
    with pytest.raises(FacilityTrustAnchorCredentialNotPresentError):
        await second_handler(
            RemoveFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- lifecycle guard ----------


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_decommissioned_raises_cannot() -> (
    None
):
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)
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

    deps = _remove_deps(event_store=store)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(FacilityCannotAddTrustAnchorCredentialError):
        await handler(
            RemoveFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- authz deny ----------


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_denied_raises_unauthorized() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)
    deps = _remove_deps(event_store=store, deny=True)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RemoveFacilityTrustAnchorCredential(
                facility_id=facility_id,
                credential_id=_CREDENTIAL_ID,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_remove_facility_trust_anchor_credential_handler_denied_writes_nothing() -> None:
    store = InMemoryEventStore()
    facility_id = await _seed_site_facility_with_trust_anchor(store)
    deps = _remove_deps(event_store=store, deny=True)
    handler = remove_facility_trust_anchor_credential.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RemoveFacilityTrustAnchorCredential(
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
