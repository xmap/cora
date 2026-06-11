"""Unit tests for the `remove_assembly_presents_as` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import UnauthorizedError
from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyPresentsAsAdded,
    AssemblyRolePresentsAsNotPresentError,
    event_type_name,
    to_payload,
)
from cora.equipment.features import remove_assembly_presents_as
from cora.equipment.features.remove_assembly_presents_as import RemoveAssemblyPresentsAs
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-000000008fd1")
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000008fd2")
_ROLE_ID = UUID("01900000-0000-7000-8000-000000008fd3")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fd0")
_SEED_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fd4")
_REMOVE_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fd5")
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


async def _seed_assembly_with_role(store: InMemoryEventStore) -> None:
    genesis = AssemblyDefined(
        assembly_id=_ASSEMBLY_ID,
        name=AssemblyName("MCTOptics"),
        presents_as_family_id=_FAMILY_ID,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="abc",
        occurred_at=_NOW,
    )
    add = AssemblyPresentsAsAdded(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID, occurred_at=_NOW)
    for event, eid in [(genesis, _SEED_GENESIS_EVENT_ID), (add, _SEED_ADD_EVENT_ID)]:
        await store.append(
            stream_type="Assembly",
            stream_id=_ASSEMBLY_ID,
            expected_version=(await store.load("Assembly", _ASSEMBLY_ID))[1],
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
async def test_handler_appends_assembly_presents_as_removed_event() -> None:
    store = InMemoryEventStore()
    await _seed_assembly_with_role(store)
    deps = _build_deps(event_store=store)
    handler = remove_assembly_presents_as.bind(deps)

    await handler(
        RemoveAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Assembly", _ASSEMBLY_ID)
    assert version == 3
    remove_event = events[-1]
    assert remove_event.event_type == "AssemblyPresentsAsRemoved"
    assert remove_event.payload == {
        "assembly_id": str(_ASSEMBLY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert remove_event.metadata == {"command": "RemoveAssemblyPresentsAs"}


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_assembly_with_role(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = remove_assembly_presents_as.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RemoveAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_assembly_not_found_when_stream_is_empty() -> None:
    deps = _build_deps()
    handler = remove_assembly_presents_as.bind(deps)

    with pytest.raises(AssemblyNotFoundError):
        await handler(
            RemoveAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_not_present_strict_not_idempotent() -> None:
    """Assembly defined but Role never advertised -> raises."""
    store = InMemoryEventStore()
    genesis = AssemblyDefined(
        assembly_id=_ASSEMBLY_ID,
        name=AssemblyName("MCTOptics"),
        presents_as_family_id=_FAMILY_ID,
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="abc",
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Assembly",
        stream_id=_ASSEMBLY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineAssembly",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    deps = _build_deps(event_store=store)
    handler = remove_assembly_presents_as.bind(deps)

    with pytest.raises(AssemblyRolePresentsAsNotPresentError):
        await handler(
            RemoveAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
