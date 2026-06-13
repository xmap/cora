"""Unit tests for the `deprecate_family` application handler.

Mirror of `test_version_family_handler.py` (single-field
command, no version_tag). Tests cover both source states + the
strict-not-idempotent re-deprecate guard.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.equipment import EquipmentHandlers, UnauthorizedError, wire_equipment
from cora.equipment.aggregates.family import (
    FamilyCannotDeprecateError,
    FamilyNotFoundError,
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
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000cb01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000cb04")
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

    result = await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_capability_deprecated_event_from_defined() -> None:
    """Direct deprecation (no prior version)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", family_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyDeprecated",
    ]
    deprecated = events[1]
    # FixedIdGenerator: defining consumes _DEFINED_EVENT_ID (the stream id is
    # derived from the name), then deprecate consumes _VERSIONED_EVENT_ID
    # (intended for versioning, but skipped here; the next id from the list).
    assert deprecated.event_id == _VERSIONED_EVENT_ID
    assert deprecated.metadata == {"command": "DeprecateFamily"}


@pytest.mark.unit
async def test_handler_appends_capability_deprecated_event_from_versioned() -> None:
    """Full lifecycle: define → version → deprecate."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="v2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Family", family_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyVersioned",
        "FamilyDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == _DEPRECATED_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_capability_does_not_exist() -> None:
    deps = _build_deps()
    handler = deprecate_family.bind(deps)

    with pytest.raises(FamilyNotFoundError):
        await handler(
            DeprecateFamily(family_id=_CAPABILITY_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    family_id = await _define_family_helper(deps)

    handler = deprecate_family.bind(deps)
    await handler(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(FamilyCannotDeprecateError):
        await handler(
            DeprecateFamily(family_id=family_id),
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
        await deprecate_family.bind(deny_deps)(
            DeprecateFamily(family_id=family_id),
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

    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Family", family_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_equipment_includes_deprecate_family() -> None:
    deps = _build_deps()
    handlers = wire_equipment(deps)
    assert isinstance(handlers, EquipmentHandlers)
    assert callable(handlers.deprecate_family)
