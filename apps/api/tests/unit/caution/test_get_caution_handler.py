"""Application-handler tests for `get_caution` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionStatus,
    event_type_name,
    to_payload,
)
from cora.caution.aggregates.caution.events import CautionRegistered
from cora.caution.errors import UnauthorizedError
from cora.caution.features import get_caution
from cora.caution.features.get_caution import GetCaution
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAUTION_ID = UUID("01900000-0000-7000-8000-000000050001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000050002")
_ASSET_ID = UUID("01900000-0000-7000-8000-000000050003")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000050004"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed(store: InMemoryEventStore) -> None:
    genesis = CautionRegistered(
        caution_id=_CAUTION_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="hexapod stalls",
        workaround="run slower",
        tags=frozenset({"motion"}),
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


@pytest.mark.unit
async def test_handler_returns_caution_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_caution.bind(deps)
    caution = await handler(
        GetCaution(caution_id=_CAUTION_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert caution is not None
    assert caution.id == _CAUTION_ID
    assert caution.status == CautionStatus.ACTIVE
    assert caution.target == AssetTarget(asset_id=_ASSET_ID)
    assert caution.text.value == "hexapod stalls"
    assert caution.workaround.value == "run slower"


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_caution.bind(deps)
    caution = await handler(
        GetCaution(caution_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert caution is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_caution.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetCaution(caution_id=_CAUTION_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
