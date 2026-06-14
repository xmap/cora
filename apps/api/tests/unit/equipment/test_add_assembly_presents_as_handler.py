"""Unit tests for the `add_assembly_presents_as` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import UnauthorizedError
from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyName,
    AssemblyNotFoundError,
    AssemblyRolePresentsAsAlreadyError,
    event_type_name,
    to_payload,
)
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.equipment.features import add_assembly_presents_as
from cora.equipment.features.add_assembly_presents_as import AddAssemblyPresentsAs
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-000000008fb1")
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000008fb2")
_ROLE_ID = UUID("01900000-0000-7000-8000-000000008fc1")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fa0")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fc3")
_RETRY_EVENT_ID = UUID("01900000-0000-7000-8000-000000008fc4")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_ADD_EVENT_ID, _RETRY_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_microscope_assembly(store: InMemoryEventStore) -> None:
    """Pre-seed a minimal Microscope Assembly via direct event append."""
    event = AssemblyDefined(
        assembly_id=_ASSEMBLY_ID,
        name=AssemblyName("Microscope"),
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
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineAssembly",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


def _seed_role_lookup(deps: Kernel) -> None:
    lookup = deps.role_lookup
    assert hasattr(lookup, "register"), "deps.role_lookup must be in-memory"
    lookup.register(  # type: ignore[union-attr]
        role_id=_ROLE_ID,
        name="Detector",
        required_affordances=frozenset({"Imageable"}),
    )


@pytest.mark.unit
async def test_handler_appends_assembly_presents_as_added_event() -> None:
    store = InMemoryEventStore()
    await _seed_microscope_assembly(store)
    deps = _build_deps(event_store=store)
    _seed_role_lookup(deps)
    handler = add_assembly_presents_as.bind(deps)

    await handler(
        AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Assembly", _ASSEMBLY_ID)
    assert version == 2
    add_event = events[-1]
    assert add_event.event_type == "AssemblyPresentsAsAdded"
    assert add_event.payload == {
        "assembly_id": str(_ASSEMBLY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert add_event.metadata == {"command": "AddAssemblyPresentsAs"}


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_microscope_assembly(store)
    deps = _build_deps(event_store=store, deny=True)
    _seed_role_lookup(deps)
    handler = add_assembly_presents_as.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_role_not_found_when_lookup_misses() -> None:
    store = InMemoryEventStore()
    await _seed_microscope_assembly(store)
    deps = _build_deps(event_store=store)
    # Skip seeding role lookup -> RoleNotFoundError.
    handler = add_assembly_presents_as.bind(deps)

    with pytest.raises(RoleNotFoundError):
        await handler(
            AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_assembly_not_found_when_stream_is_empty() -> None:
    deps = _build_deps()
    _seed_role_lookup(deps)
    handler = add_assembly_presents_as.bind(deps)

    with pytest.raises(AssemblyNotFoundError):
        await handler(
            AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_already_advertised_on_retry() -> None:
    """Strict-not-idempotent: re-adding raises."""
    store = InMemoryEventStore()
    await _seed_microscope_assembly(store)
    deps = _build_deps(event_store=store)
    _seed_role_lookup(deps)
    handler = add_assembly_presents_as.bind(deps)

    await handler(
        AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(AssemblyRolePresentsAsAlreadyError):
        await handler(
            AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
