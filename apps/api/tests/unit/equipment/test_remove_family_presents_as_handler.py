"""Unit tests for the `remove_family_presents_as` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import UnauthorizedError
from cora.equipment.aggregates.family import (
    Affordance,
    FamilyDefined,
    FamilyNotFoundError,
    FamilyPresentsAsAdded,
    FamilyRolePresentsAsNotPresentError,
    event_type_name,
    to_payload,
)
from cora.equipment.features import remove_family_presents_as
from cora.equipment.features.remove_family_presents_as import RemoveFamilyPresentsAs
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000007fd1")
_ROLE_ID = UUID("01900000-0000-7000-8000-000000007fd2")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fd0")
_SEED_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fd1")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fd5")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_REMOVE_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_camera_family_with_imager_role(store: InMemoryEventStore) -> None:
    """Pre-seed a Camera Family that advertises Imager Role."""
    genesis = FamilyDefined(
        family_id=_FAMILY_ID,
        name="Camera",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.IMAGEABLE}),
    )
    add = FamilyPresentsAsAdded(family_id=_FAMILY_ID, role_id=_ROLE_ID, occurred_at=_NOW)
    for event, eid in [(genesis, _SEED_GENESIS_EVENT_ID), (add, _SEED_ADD_EVENT_ID)]:
        await store.append(
            stream_type="Family",
            stream_id=_FAMILY_ID,
            expected_version=(await store.load("Family", _FAMILY_ID))[1],
            events=[
                to_new_event(
                    event_type=event_type_name(event),
                    payload=to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=eid,
                    command_name="seed",
                    correlation_id=_CORRELATION_ID,
                    causation_id=None,
                    principal_id=_PRINCIPAL_ID,
                )
            ],
        )


@pytest.mark.unit
async def test_handler_appends_family_presents_as_removed_event() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family_with_imager_role(store)
    deps = _build_deps(event_store=store)
    handler = remove_family_presents_as.bind(deps)

    await handler(
        RemoveFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", _FAMILY_ID)
    assert version == 3
    remove_event = events[-1]
    assert remove_event.event_type == "FamilyPresentsAsRemoved"
    assert remove_event.payload == {
        "family_id": str(_FAMILY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert remove_event.metadata == {"command": "RemoveFamilyPresentsAs"}


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family_with_imager_role(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = remove_family_presents_as.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RemoveFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_family_not_found_when_stream_is_empty() -> None:
    deps = _build_deps()
    handler = remove_family_presents_as.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            RemoveFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_not_present_strict_not_idempotent() -> None:
    """Family exists but never advertised this Role -> raises."""
    store = InMemoryEventStore()
    # Seed only the genesis; do NOT add the Role.
    genesis = FamilyDefined(
        family_id=_FAMILY_ID,
        name="Camera",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.IMAGEABLE}),
    )
    await store.append(
        stream_type="Family",
        stream_id=_FAMILY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineFamily",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = remove_family_presents_as.bind(deps)

    with pytest.raises(FamilyRolePresentsAsNotPresentError):
        await handler(
            RemoveFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
