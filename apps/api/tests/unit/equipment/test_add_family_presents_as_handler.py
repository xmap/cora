"""Unit tests for the `add_family_presents_as` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import UnauthorizedError
from cora.equipment.aggregates.family import (
    Affordance,
    FamilyAlreadyExistsError,
    FamilyCannotPresentAsError,
    FamilyDefined,
    FamilyNotFoundError,
    FamilyRolePresentsAsAlreadyError,
    event_type_name,
    to_payload,
)
from cora.equipment.aggregates.role import RoleNotFoundError
from cora.equipment.features import add_family_presents_as
from cora.equipment.features.add_family_presents_as import AddFamilyPresentsAs
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-000000007fb1")
_ROLE_ID = UUID("01900000-0000-7000-8000-000000007fc1")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fa0")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fc3")
_RETRY_EVENT_ID = UUID("01900000-0000-7000-8000-000000007fc4")
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


async def _seed_camera_family(store: InMemoryEventStore) -> None:
    """Pre-seed a Camera Family with Imageable affordance."""
    event = FamilyDefined(
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
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineFamily",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


def _seed_role_lookup(deps: Kernel, *, required: frozenset[str]) -> None:
    """Register the Role on the InMemoryRoleLookup adapter."""
    lookup = deps.role_lookup
    assert hasattr(lookup, "register"), "deps.role_lookup must be in-memory"
    lookup.register(  # type: ignore[union-attr]
        role_id=_ROLE_ID,
        name="Imager",
        required_affordances=required,
    )


@pytest.mark.unit
async def test_handler_appends_family_presents_as_added_event() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family(store)
    deps = _build_deps(event_store=store)
    _seed_role_lookup(deps, required=frozenset({"Imageable"}))
    handler = add_family_presents_as.bind(deps)

    await handler(
        AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", _FAMILY_ID)
    assert version == 2
    add_event = events[-1]
    assert add_event.event_type == "FamilyPresentsAsAdded"
    assert add_event.payload == {
        "family_id": str(_FAMILY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert add_event.metadata == {"command": "AddFamilyPresentsAs"}


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family(store)
    deps = _build_deps(event_store=store, deny=True)
    _seed_role_lookup(deps, required=frozenset({"Imageable"}))
    handler = add_family_presents_as.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, _ = await store.load("Family", _FAMILY_ID)
    assert len(events) == 1  # genesis only; no add appended


@pytest.mark.unit
async def test_handler_raises_role_not_found_when_role_lookup_misses() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family(store)
    deps = _build_deps(event_store=store)
    # NOTE: skip _seed_role_lookup so the lookup returns None.
    handler = add_family_presents_as.bind(deps)

    with pytest.raises(RoleNotFoundError):
        await handler(
            AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_family_not_found_when_stream_is_empty() -> None:
    deps = _build_deps()
    _seed_role_lookup(deps, required=frozenset())
    handler = add_family_presents_as.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_present_as_when_affordances_missing() -> None:
    store = InMemoryEventStore()
    await _seed_camera_family(store)
    deps = _build_deps(event_store=store)
    _seed_role_lookup(deps, required=frozenset({"Imageable", "Binnable"}))
    handler = add_family_presents_as.bind(deps)

    with pytest.raises(FamilyCannotPresentAsError) as exc:
        await handler(
            AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.missing_affordances == frozenset({Affordance.BINNABLE})


@pytest.mark.unit
async def test_handler_raises_already_advertised_on_retry() -> None:
    """Strict-not-idempotent: re-adding raises FamilyRolePresentsAsAlreadyError."""
    store = InMemoryEventStore()
    await _seed_camera_family(store)
    deps = _build_deps(event_store=store)
    _seed_role_lookup(deps, required=frozenset({"Imageable"}))
    handler = add_family_presents_as.bind(deps)

    # First add succeeds
    await handler(
        AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second add raises
    # Re-build deps so the id generator has a fresh slot for the retry's
    # logging event id (only matters if we use it; tolerated either way).
    with pytest.raises(FamilyRolePresentsAsAlreadyError):
        await handler(
            AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_uses_existing_family_already_exists_error_unchanged() -> None:
    """Sanity: FamilyAlreadyExistsError is reachable from this module."""
    # Import-time check; not a runtime test, just ensures rename safety.
    _ = FamilyAlreadyExistsError
