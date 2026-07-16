"""Application-handler tests for the `grant_allocation` slice.

Single-stream genesis: every successful call writes ONE
`AllocationGranted` event on the Allocation stream. The slice's
wrinkle over the plain create-style template is the optional
caller-supplied `allocation_id`: the handler loads the target stream
first so a collision trips the decider's genesis guard. The handler
also stamps `granted_by` from the envelope's principal (the
fold-symmetry attribution half).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.budget.aggregates.allocation import (
    AllocationAlreadyExistsError,
    AllocationGranted,
    event_type_name,
    to_payload,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features import grant_allocation
from cora.budget.features.grant_allocation import GrantAllocation
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000c001")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000c002")
_SUPPLIED_ID = UUID("01900000-0000-7000-8000-00000000c003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    ids: list[UUID] | None = None,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        # grant_allocation consumes 2 ids on the minted path: new
        # allocation_id + 1 event_id. Caller-supplied-id tests pass
        # ids=[_EVENT_ID] only.
        ids=ids if ids is not None else [_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> GrantAllocation:
    base: dict[str, object] = {
        "ceiling_usd": 25000.0,
        "note": "FY26 imaging award",
    }
    base.update(overrides)
    return GrantAllocation(**base)  # type: ignore[arg-type]


async def _seed_allocation(store: InMemoryEventStore, allocation_id: UUID) -> None:
    event = AllocationGranted(
        allocation_id=allocation_id,
        ceiling_usd=25000.0,
        campaign_id=None,
        note="Seeded envelope",
        granted_by=ActorId(_PRINCIPAL_ID),
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Allocation",
        stream_id=allocation_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="GrantAllocation",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_returns_generated_allocation_id() -> None:
    deps = _build_deps()
    handler = grant_allocation.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_uses_caller_supplied_allocation_id() -> None:
    """A command-carried id is used verbatim; the IdGenerator only mints
    the event envelope id."""
    store = InMemoryEventStore()
    deps = _build_deps(ids=[_EVENT_ID], event_store=store)
    handler = grant_allocation.bind(deps)
    result = await handler(
        _command(allocation_id=_SUPPLIED_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _SUPPLIED_ID
    events, version = await store.load("Allocation", _SUPPLIED_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_appends_single_granted_event_with_principal_as_granted_by() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = grant_allocation.bind(deps)
    await handler(
        _command(campaign_id=UUID("01900000-0000-7000-8000-000000000044")),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Allocation", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    assert events[0].event_type == "AllocationGranted"
    payload = events[0].payload
    assert payload["allocation_id"] == str(_NEW_ID)
    assert payload["ceiling_usd"] == 25000.0
    assert payload["campaign_id"] == "01900000-0000-7000-8000-000000000044"
    assert payload["note"] == "FY26 imaging award"
    assert payload["granted_by"] == str(_PRINCIPAL_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_handler_propagates_envelope_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = grant_allocation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Allocation", _NEW_ID)
    stored = events[0]
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_supplied_id_collision_raises_already_exists() -> None:
    """The handler loads the target stream, so re-granting a
    caller-supplied id trips the decider's genesis guard instead of
    surfacing a raw concurrency error."""
    store = InMemoryEventStore()
    await _seed_allocation(store, _SUPPLIED_ID)
    deps = _build_deps(ids=[_EVENT_ID], event_store=store)
    handler = grant_allocation.bind(deps)
    with pytest.raises(AllocationAlreadyExistsError):
        await handler(
            _command(allocation_id=_SUPPLIED_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Allocation", _SUPPLIED_ID)
    assert version == 1
    assert len(events) == 1


@pytest.mark.unit
async def test_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = grant_allocation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_denied_does_not_write_stream() -> None:
    """Authorize-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = grant_allocation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    events, version = await store.load("Allocation", _NEW_ID)
    assert version == 0
    assert events == []
