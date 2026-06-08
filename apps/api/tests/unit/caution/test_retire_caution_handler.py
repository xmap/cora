"""Application-handler tests for `retire_caution` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionNotFoundError,
    CautionRetireReason,
    event_type_name,
    to_payload,
)
from cora.caution.aggregates.caution.events import CautionRegistered
from cora.caution.errors import UnauthorizedError
from cora.caution.features import retire_caution
from cora.caution.features.retire_caution import RetireCaution
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAUTION_ID = UUID("01900000-0000-7000-8000-000000040001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000040002")
_RETIRED_EVENT_ID = UUID("01900000-0000-7000-8000-000000040003")
_ASSET_ID = UUID("01900000-0000-7000-8000-000000040004")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000040005"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed(store: InMemoryEventStore) -> None:
    genesis = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="text",
        workaround="workaround",
        tags=frozenset(),
        authored_by=_AUTHOR_ID,
        expires_at=None,
        propagate_to_children=False,
        parent_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(genesis),
        payload=to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=_GENESIS_EVENT_ID,
        command_name="RegisterCaution",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_AUTHOR_ID,
    )
    await store.append(
        stream_type="Caution",
        stream_id=_CAUTION_ID,
        expected_version=0,
        events=[new_event],
    )


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_RETIRED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_handler_appends_retired_event_on_active_state() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store)
    handler = retire_caution.bind(deps)
    await handler(
        RetireCaution(caution_id=_CAUTION_ID, reason=CautionRetireReason.RESOLVED),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Caution", _CAUTION_ID)
    assert version == 2
    assert events[1].event_type == "CautionRetired"
    assert events[1].payload["reason"] == "Resolved"
    assert events[1].principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_not_found_on_empty_stream() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = retire_caution.bind(deps)
    missing = uuid4()
    with pytest.raises(CautionNotFoundError) as exc_info:
        await handler(
            RetireCaution(caution_id=missing, reason=CautionRetireReason.RESOLVED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.caution_id == missing


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = retire_caution.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RetireCaution(caution_id=_CAUTION_ID, reason=CautionRetireReason.RESOLVED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = retire_caution.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            RetireCaution(caution_id=_CAUTION_ID, reason=CautionRetireReason.RESOLVED),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Caution", _CAUTION_ID)
    assert version == 1  # still just the genesis
