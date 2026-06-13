"""Unit tests for the `version_family` application handler.

Longhand handler (logs version_tag for diagnostic visibility). Tests
cover the multi-source guard, defensive version_tag validation, auth
deny, causation_id propagation, and wire smoke.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import (
    FamilyCannotVersionError,
    FamilyNotFoundError,
    InvalidFamilyVersionTagError,
)
from cora.equipment.features import (
    define_family,
    deprecate_family,
    version_family,
)
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.deprecate_family import DeprecateFamily
from cora.equipment.features.version_family import VersionFamily
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000ca01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ca04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Thin wrapper preserving this file's ID list + clock."""
    # define_family derives its stream id from the name, so the generator
    # supplies only event ids here (_CAPABILITY_ID stays as the unknown id
    # for the not-found test).
    return _build_deps_shared(
        ids=[_DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _define_family_helper(deps: Kernel) -> UUID:
    return await define_family.bind(deps)(
        DefineFamily(name="Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    result = await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_capability_versioned_event_with_version_tag() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", family_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyVersioned",
    ]
    versioned = events[1]
    assert versioned.event_id == _VERSIONED_EVENT_ID
    assert versioned.metadata == {"command": "VersionFamily"}
    assert versioned.payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_supports_re_versioning() -> None:
    """Defined → Versioned → Versioned (subsequent revision)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)
    handler = version_family.bind(deps)

    await handler(
        VersionFamily(family_id=family_id, version_tag="v1", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", family_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyVersioned",
        "FamilyVersioned",
    ]
    assert events[1].payload["version_tag"] == "v1"
    assert events[2].payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_capability_does_not_exist() -> None:
    deps = _build_deps()
    handler = version_family.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            VersionFamily(family_id=_CAPABILITY_ID, version_tag="v1", affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_version_tag_for_whitespace_only() -> None:
    """Defensive validation in the decider; pinned at handler layer."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    with pytest.raises(InvalidFamilyVersionTagError):
        await version_family.bind(deps)(
            VersionFamily(family_id=family_id, version_tag="   ", affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(FamilyCannotVersionError):
        await version_family.bind(deps)(
            VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    deny_deps = _build_deps(event_store=store, deny=True)
    with pytest.raises(UnauthorizedError) as exc_info:
        await version_family.bind(deny_deps)(
            VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Family", family_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_version_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.version_family)
