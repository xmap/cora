"""Unit tests for the `version_method` application handler.

Mirror of `test_version_family_handler.py` (Equipment 5f-2).
Longhand handler (logs version_tag).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.method import (
    ExecutionPattern,
    InvalidMethodVersionTagError,
    MethodCannotVersionError,
    MethodNotFoundError,
)
from cora.recipe.features import define_method, deprecate_method, version_method
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.deprecate_method import DeprecateMethod
from cora.recipe.features.version_method import VersionMethod
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_METHOD_ID = UUID("01900000-0000-7000-8000-00000000ad01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ad02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ad03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ad04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000ad0c")


async def _define_method_helper(deps: Kernel) -> UUID:
    """Seed bound Capability + invoke define_method."""
    await seed_capability(deps.event_store, _CAPABILITY_ID)
    return await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            name="XRF Mapping",
            capability_id=_CAPABILITY_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    result = await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_method_versioned_event_with_version_tag() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 2
    assert [e.event_type for e in events] == ["MethodDefined", "MethodVersioned"]
    versioned = events[1]
    assert versioned.event_id == _VERSIONED_EVENT_ID
    assert versioned.metadata == {"command": "VersionMethod"}
    assert versioned.payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_supports_re_versioning() -> None:
    """Defined → Versioned → Versioned (subsequent revision)."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)
    handler = version_method.bind(deps)

    await handler(
        VersionMethod(method_id=method_id, version_tag="v1"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        VersionMethod(method_id=method_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Method", method_id)
    assert version == 3
    assert events[1].payload["version_tag"] == "v1"
    assert events[2].payload["version_tag"] == "v2"


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_method_does_not_exist() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID], now=_NOW
    )
    handler = version_method.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            VersionMethod(method_id=_METHOD_ID, version_tag="v1"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_version_tag_for_whitespace_only() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    with pytest.raises(InvalidMethodVersionTagError):
        await version_method.bind(deps)(
            VersionMethod(method_id=method_id, version_tag="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_version_when_deprecated() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    await deprecate_method.bind(deps)(
        DeprecateMethod(method_id=method_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(MethodCannotVersionError):
        await version_method.bind(deps)(
            VersionMethod(method_id=method_id, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    deny_deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await version_method.bind(deny_deps)(
            VersionMethod(method_id=method_id, version_tag="v2"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    method_id = await _define_method_helper(deps)

    await version_method.bind(deps)(
        VersionMethod(method_id=method_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Method", method_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_version_method() -> None:
    deps = build_deps(
        ids=[_METHOD_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID], now=_NOW
    )
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.version_method)
