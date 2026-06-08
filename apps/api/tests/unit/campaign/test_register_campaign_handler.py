"""Application-handler tests for `register_campaign` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features import register_campaign
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.shared.identifier import Identifier
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000f001")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000f002")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000f003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000f099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> RegisterCampaign:
    base: dict[str, object] = {
        "name": "In-situ heating series",
        "intent": CampaignIntent.SERIES,
        "lead_actor_id": _LEAD_ACTOR_ID,
    }
    base.update(overrides)
    return RegisterCampaign(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_handler_returns_generated_campaign_id() -> None:
    deps = _build_deps()
    handler = register_campaign.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_campaign_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_campaign.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Campaign", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "CampaignRegistered"
    assert stored.payload["campaign_id"] == str(_NEW_ID)
    assert stored.payload["name"] == "In-situ heating series"
    assert stored.payload["intent"] == "Series"
    assert stored.payload["lead_actor_id"] == str(_LEAD_ACTOR_ID)
    assert stored.payload["subject_id"] is None
    assert stored.payload["description"] is None
    assert stored.payload["tags"] == []
    assert stored.payload["external_refs"] == []
    assert stored.payload["external_id"] is None
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _EVENT_ID
    assert stored.principal_id == _PRINCIPAL_ID
    assert stored.metadata == {"command": "RegisterCampaign"}


@pytest.mark.unit
async def test_handler_serializes_external_refs_sorted() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_campaign.bind(deps)
    refs = frozenset(
        {
            Identifier(scheme="visit", value="V-77"),
            Identifier(scheme="proposal", value="2025-100"),
        }
    )
    await handler(
        _command(external_refs=refs),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Campaign", _NEW_ID)
    assert events[0].payload["external_refs"] == [
        {"scheme": "proposal", "value": "2025-100"},
        {"scheme": "visit", "value": "V-77"},
    ]


@pytest.mark.unit
async def test_handler_serializes_tags_sorted() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_campaign.bind(deps)
    await handler(
        _command(tags=frozenset({"zeta", "alpha", "mu"})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Campaign", _NEW_ID)
    assert events[0].payload["tags"] == ["alpha", "mu", "zeta"]


@pytest.mark.unit
async def test_handler_passes_through_lead_actor_id_distinct_from_principal() -> None:
    """Campaign keeps `lead_actor_id` on the command surface; the
    handler does NOT derive it from envelope (unlike Caution's
    authored_by)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = register_campaign.bind(deps)
    distinct_lead = UUID("01900000-0000-7000-8000-00000000fdef")
    await handler(
        _command(lead_actor_id=distinct_lead),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Campaign", _NEW_ID)
    assert events[0].payload["lead_actor_id"] == str(distinct_lead)
    assert events[0].principal_id == _PRINCIPAL_ID  # envelope unchanged


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = register_campaign.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = register_campaign.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Campaign", _NEW_ID)
    assert version == 0
    assert events == []
