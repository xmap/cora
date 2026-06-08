"""Application-handler tests for the `register_facility` slice.

Pins single-stream genesis (FacilityRegistered on the Facility stream,
no Decision audit cross-write per [[project_facility_aggregate_design]]
Lock "No cross-BC atomic-writes in slice 5"), stream-id derivation
from FacilityCode (deterministic UUID5), ConcurrencyError ->
FacilityAlreadyExistsError translation on duplicate-code race, and
authz-deny passes UnauthorizedError without writing.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import (
    FacilityAlreadyExistsError,
    FacilityKind,
    facility_stream_id,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import register_facility
from cora.federation.features.register_facility import RegisterFacility
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.kernel import Kernel
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=UTC)
_FACILITY_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed201")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed299")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed2aa")
_CODE = "aps"
_AREA_CODE = "2-bm"
_PARENT_FACILITY_ID = FacilityId(UUID("01900000-0000-7000-8000-000000fed103"))


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    facility_lookup: InMemoryFacilityLookup | None = None,
) -> Kernel:
    # register_facility consumes 1 id (the FacilityRegistered event_id);
    # the Facility stream_id derives from FacilityCode via facility_stream_id,
    # NOT from id_generator.
    return _build_deps_shared(
        ids=[_FACILITY_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
        facility_lookup=facility_lookup,
    )


def _facility_lookup_with_site_parent() -> InMemoryFacilityLookup:
    """Test helper: seed an InMemoryFacilityLookup with a Site-tier
    parent at _PARENT_FACILITY_ID for Area-registration tests."""
    lookup = InMemoryFacilityLookup()
    lookup.register(
        facility_id=_PARENT_FACILITY_ID,
        code="aps",
        kind=FacilityKind.SITE.value,
    )
    return lookup


def _site_command(**overrides: object) -> RegisterFacility:
    base: dict[str, object] = {
        "code": _CODE,
        "display_name": "Advanced Photon Source",
        "kind": FacilityKind.SITE,
        "parent_id": None,
    }
    base.update(overrides)
    return RegisterFacility(**base)  # type: ignore[arg-type]


def _area_command(**overrides: object) -> RegisterFacility:
    base: dict[str, object] = {
        "code": _AREA_CODE,
        "display_name": "2-BM Beamline",
        "kind": FacilityKind.AREA,
        "parent_id": _PARENT_FACILITY_ID,
    }
    base.update(overrides)
    return RegisterFacility(**base)  # type: ignore[arg-type]


# ---------- happy path: returns derived facility_id ----------


@pytest.mark.unit
async def test_register_facility_handler_returns_derived_facility_id() -> None:
    """The facility_id returned by the handler MUST equal facility_stream_id(code)."""
    deps = _build_deps()
    handler = register_facility.bind(deps)
    result = await handler(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == facility_stream_id(FacilityCode(_CODE))


@pytest.mark.unit
async def test_register_facility_handler_appends_to_facility_stream_only() -> None:
    """Single-stream write per design memo: FacilityRegistered on Facility
    stream; NO DecisionRegistered audit cross-write."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_facility.bind(deps)
    await handler(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    facility_id = facility_stream_id(FacilityCode(_CODE))
    facility_events, facility_version = await store.load("Facility", facility_id)
    assert facility_version == 1
    assert len(facility_events) == 1
    assert facility_events[0].event_type == "FacilityRegistered"


@pytest.mark.unit
async def test_register_facility_handler_does_not_write_decision_stream() -> None:
    """Per design memo: register_facility does NOT emit Decision audit.
    No Decision stream is created by this handler."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_facility.bind(deps)
    await handler(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # The InMemoryEventStore only contains the one Facility stream;
    # an empty Decision load returns (events=[], version=0).
    decision_events, decision_version = await store.load(
        "Decision", UUID("00000000-0000-0000-0000-000000000099")
    )
    assert decision_version == 0
    assert decision_events == []


@pytest.mark.unit
async def test_register_facility_handler_payload_carries_command_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_facility.bind(deps)
    await handler(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    facility_id = facility_stream_id(FacilityCode(_CODE))
    facility_events, _version = await store.load("Facility", facility_id)
    payload = facility_events[0].payload
    assert payload["code"] == _CODE
    assert payload["display_name"] == "Advanced Photon Source"
    assert payload["kind"] == "Site"
    assert payload["parent_id"] is None
    assert payload["registered_by"] == str(_PRINCIPAL_ID)


# ---------- deterministic stream-id derivation ----------


@pytest.mark.unit
async def test_register_facility_handler_uses_deterministic_stream_id() -> None:
    """The Facility stream_id is derived from FacilityCode via UUID5;
    callers can predict it without consulting the handler return."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_facility.bind(deps)
    returned_id = await handler(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    expected = facility_stream_id(FacilityCode(_CODE))
    assert returned_id == expected


# ---------- ConcurrencyError -> FacilityAlreadyExistsError translation ----------


@pytest.mark.unit
async def test_register_facility_handler_duplicate_code_raises_already_exists() -> None:
    """Second register with the same code collides on the derived stream_id
    and append_expected_version=0; handler translates ConcurrencyError to
    FacilityAlreadyExistsError for the route to surface as 409."""
    store = InMemoryEventStore()
    deps_first = _build_deps_shared(
        ids=[_FACILITY_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    handler_first = register_facility.bind(deps_first)
    await handler_first(
        _site_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Build fresh deps with a new event_id; same store + same code.
    deps_second = _build_deps_shared(
        ids=[UUID("01900000-0000-7000-8000-000000fed2bb")],
        now=_NOW,
        event_store=store,
    )
    handler_second = register_facility.bind(deps_second)
    with pytest.raises(FacilityAlreadyExistsError) as exc:
        await handler_second(
            _site_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.code == FacilityCode(_CODE)


# ---------- authz deny ----------


@pytest.mark.unit
async def test_register_facility_handler_denied_raises_unauthorized() -> None:
    deps = _build_deps(deny=True)
    handler = register_facility.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _site_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_register_facility_handler_denied_writes_nothing() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_facility.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _site_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    facility_id = facility_stream_id(FacilityCode(_CODE))
    events, version = await store.load("Facility", facility_id)
    assert version == 0
    assert events == []


# ---------- Area command ----------


@pytest.mark.unit
async def test_register_facility_handler_area_carries_parent_id() -> None:
    store = InMemoryEventStore()
    facility_lookup = _facility_lookup_with_site_parent()
    deps = _build_deps(event_store=store, facility_lookup=facility_lookup)
    handler = register_facility.bind(deps)
    await handler(
        _area_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    facility_id = facility_stream_id(FacilityCode(_AREA_CODE))
    facility_events, _version = await store.load("Facility", facility_id)
    payload = facility_events[0].payload
    assert payload["kind"] == "Area"
    assert payload["parent_id"] == str(_PARENT_FACILITY_ID)


@pytest.mark.unit
async def test_register_facility_handler_area_with_missing_parent_raises() -> None:
    """Slice 6 Sub-Slice A: handler calls FacilityLookup; missing parent
    surfaces FacilityParentNotFoundError (route maps to 404)."""
    from cora.federation.aggregates.facility import FacilityParentNotFoundError

    store = InMemoryEventStore()
    # facility_lookup defaults to empty InMemoryFacilityLookup; parent_id
    # lookup returns None.
    deps = _build_deps(event_store=store)
    handler = register_facility.bind(deps)
    with pytest.raises(FacilityParentNotFoundError):
        await handler(
            _area_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_register_facility_handler_area_with_area_parent_raises() -> None:
    """Slice 6 Sub-Slice A: handler calls FacilityLookup; Area parent
    surfaces FacilityAreaParentMustBeSiteError (route maps to 422)."""
    from cora.federation.aggregates.facility import (
        FacilityAreaParentMustBeSiteError,
    )

    store = InMemoryEventStore()
    facility_lookup = InMemoryFacilityLookup()
    facility_lookup.register(
        facility_id=_PARENT_FACILITY_ID,
        code="2-bm-parent",
        kind=FacilityKind.AREA.value,
    )
    deps = _build_deps(event_store=store, facility_lookup=facility_lookup)
    handler = register_facility.bind(deps)
    with pytest.raises(FacilityAreaParentMustBeSiteError):
        await handler(
            _area_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
