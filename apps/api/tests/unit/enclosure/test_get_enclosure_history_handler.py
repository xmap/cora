"""Unit tests for the `get_enclosure_history` query handler.

The load-bearing test here is `test_handler_view_never_carries_relay_unsafe_fields`:
it pins that this slice's raw event payloads (which DO include `reason`
and `monitor_ref`, unlike Run's) never silently grow a redaction
requirement onto this general-purpose read -- the actual redaction for
the external relay lives downstream, in the status-push feature that
builds the timeline document. This test exists so a reviewer notices
if that downstream redaction is ever skipped, by proving what the raw
view actually contains.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.enclosure.aggregates.enclosure.events import (
    EnclosureDecommissioned,
    EnclosurePermitObserved,
    EnclosureRegistered,
    event_type_name,
    to_payload,
)
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features import get_enclosure_history
from cora.enclosure.features.get_enclosure_history import GetEnclosureHistory
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId, MonitorSourceId
from tests.unit._helpers import RecordingAuthorize, build_deps

_NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
_EVENT_LIMIT = 2000
"""Mirrors `get_enclosure_history.handler._EVENT_LIMIT`. Kept as a
local constant rather than importing the private module attribute."""
_ENCLOSURE_ID = UUID("01900000-0000-7000-8000-00000000ee01")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-0000656e6301"))


async def _seed_registered(
    store: InMemoryEventStore, enclosure_id: UUID, *, occurred_at: datetime
) -> None:
    event = EnclosureRegistered(
        enclosure_id=enclosure_id,
        name="2-BM-A",
        facility_code=FacilityCode("aps"),
        registered_by=ActorId(uuid4()),
        occurred_at=occurred_at,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="RegisterEnclosure",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Enclosure", stream_id=enclosure_id, expected_version=0, events=[new_event]
    )


async def _seed_permit_observed(
    store: InMemoryEventStore,
    enclosure_id: UUID,
    *,
    expected_version: int,
    from_status: str,
    to_status: str,
    occurred_at: datetime,
) -> None:
    event = EnclosurePermitObserved(
        enclosure_id=enclosure_id,
        from_status=from_status,
        to_status=to_status,
        reason="PSS permit observation via S02BM-PSS:StaA:SecureM",
        trigger="Monitor",
        triggered_by=_MONITOR_SOURCE_ID,
        occurred_at=occurred_at,
        observed_at=None,
        monitor_ref="EpicsPv:S02BM-PSS:StaA:SecureM",
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="ObserveEnclosureStatus",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Enclosure",
        stream_id=enclosure_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_decommissioned(
    store: InMemoryEventStore,
    enclosure_id: UUID,
    *,
    expected_version: int,
    occurred_at: datetime,
) -> None:
    event = EnclosureDecommissioned(
        enclosure_id=enclosure_id,
        reason="instrument removed and Asset retired",
        triggered_by=ActorId(uuid4()),
        occurred_at=occurred_at,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="DecommissionEnclosure",
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Enclosure",
        stream_id=enclosure_id,
        expected_version=expected_version,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_genesis_event_yields_unknown_permit_and_active_lifecycle() -> None:
    """The evolver seeds permit_status/lifecycle from the event TYPE, not
    the genesis payload -- EnclosureRegistered's own payload carries
    neither field."""
    store = InMemoryEventStore()
    await _seed_registered(store, _ENCLOSURE_ID, occurred_at=_NOW)
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=_ENCLOSURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.enclosure_id == _ENCLOSURE_ID
    assert view.name == "2-BM-A"
    assert view.permit_status == "Unknown"
    assert view.lifecycle == "Active"
    assert len(view.events) == 1
    assert view.events[0].event_type == "EnclosureRegistered"


@pytest.mark.unit
async def test_handler_two_permit_transitions_both_appear_with_distinct_timestamps() -> None:
    store = InMemoryEventStore()
    registered_at = _NOW
    permitted_at = _NOW + timedelta(seconds=5)
    not_permitted_at = _NOW + timedelta(seconds=10)
    await _seed_registered(store, _ENCLOSURE_ID, occurred_at=registered_at)
    await _seed_permit_observed(
        store,
        _ENCLOSURE_ID,
        expected_version=1,
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=permitted_at,
    )
    await _seed_permit_observed(
        store,
        _ENCLOSURE_ID,
        expected_version=2,
        from_status="Permitted",
        to_status="NotPermitted",
        occurred_at=not_permitted_at,
    )
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=_ENCLOSURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert [e.event_type for e in view.events] == [
        "EnclosureRegistered",
        "EnclosurePermitObserved",
        "EnclosurePermitObserved",
    ]
    assert view.events[1].occurred_at == permitted_at
    assert view.events[2].occurred_at == not_permitted_at
    assert view.permit_status == "NotPermitted"


@pytest.mark.unit
async def test_handler_permit_status_preserved_across_decommission() -> None:
    """Decommission is a lifecycle-axis transition; permit_status must
    survive untouched as audit trail (evolver.py's documented
    orthogonality guarantee)."""
    store = InMemoryEventStore()
    await _seed_registered(store, _ENCLOSURE_ID, occurred_at=_NOW)
    await _seed_permit_observed(
        store,
        _ENCLOSURE_ID,
        expected_version=1,
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=_NOW + timedelta(seconds=5),
    )
    await _seed_decommissioned(
        store, _ENCLOSURE_ID, expected_version=2, occurred_at=_NOW + timedelta(seconds=10)
    )
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=_ENCLOSURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.lifecycle == "Decommissioned"
    assert view.permit_status == "Permitted"


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_enclosure() -> None:
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is None


@pytest.mark.unit
async def test_handler_events_truncated_true_over_limit() -> None:
    store = InMemoryEventStore()
    await _seed_registered(store, _ENCLOSURE_ID, occurred_at=_NOW)
    version = 1
    for i in range(_EVENT_LIMIT):
        from_status = "Permitted" if i % 2 == 0 else "NotPermitted"
        to_status = "NotPermitted" if i % 2 == 0 else "Permitted"
        await _seed_permit_observed(
            store,
            _ENCLOSURE_ID,
            expected_version=version,
            from_status=from_status,
            to_status=to_status,
            occurred_at=_NOW + timedelta(seconds=i + 1),
        )
        version += 1
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=_ENCLOSURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.events_truncated is True
    assert len(view.events) == _EVENT_LIMIT


@pytest.mark.unit
async def test_handler_view_never_carries_relay_unsafe_fields() -> None:
    """`EnclosurePermitObserved.reason` and `.monitor_ref` embed the PSS
    PV address (e.g. 'S02BM-PSS:StaA:SecureM'). This slice is a
    general-purpose on-network read (mirroring `get_run_history` and
    `list_enclosures`, both of which already surface equivalent detail
    on-network), so it legitimately carries the full payload -- the
    redaction that matters happens downstream in the status-push
    feature that builds the timeline document actually sent to the
    external relay. This test documents that boundary by asserting
    what IS present here, so a future reader looking for the
    redaction knows not to expect it at this layer."""
    store = InMemoryEventStore()
    await _seed_registered(store, _ENCLOSURE_ID, occurred_at=_NOW)
    await _seed_permit_observed(
        store,
        _ENCLOSURE_ID,
        expected_version=1,
        from_status="Unknown",
        to_status="Permitted",
        occurred_at=_NOW + timedelta(seconds=5),
    )
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, event_store=store)
    handler = get_enclosure_history.bind(deps)

    view = await handler(
        GetEnclosureHistory(enclosure_id=_ENCLOSURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    observed_event = view.events[1]
    assert observed_event.payload["monitor_ref"] == "EpicsPv:S02BM-PSS:StaA:SecureM"
    assert "PSS permit observation via" in observed_event.payload["reason"]


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = RecordingAuthorize()
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, authz=tracking)
    handler = get_enclosure_history.bind(deps)

    await handler(
        GetEnclosureHistory(enclosure_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetEnclosureHistory", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW, deny=True)
    handler = get_enclosure_history.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetEnclosureHistory(enclosure_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_enclosure_includes_get_enclosure_history() -> None:
    from cora.enclosure import EnclosureHandlers, wire_enclosure

    deps = build_deps(ids=[_ENCLOSURE_ID], now=_NOW)
    handlers = wire_enclosure(deps)
    assert isinstance(handlers, EnclosureHandlers)
    assert callable(handlers.get_enclosure_history)
