"""Application-handler tests for `supersede_caution` slice.

Cross-aggregate atomic write via EventStore.append_streams: the
parent's CautionSuperseded + the child's CautionRegistered land in
one transactional batch.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionNotFoundError,
    CautionSeverity,
    event_type_name,
    to_payload,
)
from cora.caution.aggregates.caution.events import CautionRegistered
from cora.caution.errors import UnauthorizedError
from cora.caution.features import supersede_caution
from cora.caution.features.supersede_caution import SupersedeCaution
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_PARENT_ID = UUID("01900000-0000-7000-8000-000000020001")
_PARENT_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000020002")
_CHILD_ID = UUID("01900000-0000-7000-8000-000000020010")
_PARENT_SUPERSEDED_EVENT_ID = UUID("01900000-0000-7000-8000-000000020011")
_CHILD_REGISTERED_EVENT_ID = UUID("01900000-0000-7000-8000-000000020012")
_ASSET_ID = UUID("01900000-0000-7000-8000-000000020003")
_AUTHOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000020004"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_parent(store: InMemoryEventStore) -> None:
    genesis = CautionRegistered(
        caution_id=_PARENT_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category="Wear",
        severity="Caution",
        text="original",
        workaround="original workaround",
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
        event_id=_PARENT_GENESIS_EVENT_ID,
        command_name="RegisterCaution",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_AUTHOR_ID,
    )
    await store.append(
        stream_type="Caution",
        stream_id=_PARENT_ID,
        expected_version=0,
        events=[new_event],
    )


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_CHILD_ID, _PARENT_SUPERSEDED_EVENT_ID, _CHILD_REGISTERED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command() -> SupersedeCaution:
    return SupersedeCaution(
        parent_id=_PARENT_ID,
        target=AssetTarget(asset_id=_ASSET_ID),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text="updated text",
        workaround="updated workaround",
    )


@pytest.mark.unit
async def test_handler_returns_child_caution_id() -> None:
    store = InMemoryEventStore()
    await _seed_parent(store)
    deps = _build_deps(event_store=store)
    handler = supersede_caution.bind(deps)
    child_id = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert child_id == _CHILD_ID


@pytest.mark.unit
async def test_handler_writes_parent_superseded_and_child_registered_atomically() -> None:
    store = InMemoryEventStore()
    await _seed_parent(store)
    deps = _build_deps(event_store=store)
    handler = supersede_caution.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    parent_events, parent_version = await store.load("Caution", _PARENT_ID)
    assert parent_version == 2
    assert parent_events[1].event_type == "CautionSuperseded"
    assert parent_events[1].payload["superseded_by_caution_id"] == str(_CHILD_ID)

    child_events, child_version = await store.load("Caution", _CHILD_ID)
    assert child_version == 1
    assert child_events[0].event_type == "CautionRegistered"
    assert child_events[0].payload["parent_id"] == str(_PARENT_ID)
    assert child_events[0].payload["text"] == "updated text"
    assert child_events[0].payload["workaround"] == "updated workaround"


@pytest.mark.unit
async def test_handler_raises_not_found_when_parent_absent() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = supersede_caution.bind(deps)
    with pytest.raises(CautionNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_parent(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = supersede_caution.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_write_when_parent_already_superseded() -> None:
    """Second supersede of the same parent fails (Active->Superseded already happened)."""
    from cora.caution.aggregates.caution import CautionCannotSupersedeError

    store = InMemoryEventStore()
    await _seed_parent(store)
    deps = _build_deps(event_store=store)
    handler = supersede_caution.bind(deps)
    # First supersede consumes [child_id, parent_superseded_event_id, child_registered_event_id]
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Refresh deps with new id queue for the second attempt.
    deps2 = _build_deps_shared(
        ids=[uuid4(), uuid4(), uuid4()],
        now=_NOW,
        event_store=store,
    )
    handler2 = supersede_caution.bind(deps2)
    with pytest.raises(CautionCannotSupersedeError):
        await handler2(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
