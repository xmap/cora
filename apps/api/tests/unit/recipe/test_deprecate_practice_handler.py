"""Unit tests for the `deprecate_practice` application handler.

Mirror of `test_deprecate_method_handler.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.practice import (
    PracticeCannotDeprecateError,
    PracticeNotFoundError,
)
from cora.recipe.features import (
    define_practice,
    deprecate_practice,
    version_practice,
)
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.deprecate_practice import DeprecatePractice
from cora.recipe.features.version_practice import VersionPractice
from cora.shared.deprecation import DeprecationReason
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRACTICE_ID = UUID("01900000-0000-7000-8000-00000000be01")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000be02")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000be03")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000000be04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000111")
_SITE_ID = UUID("01900000-0000-7000-8000-000000000222")


async def _define_practice_helper(deps: Kernel) -> UUID:
    return await define_practice.bind(deps)(
        DefinePractice(
            name="APS Standard Tomography",
            method_id=_METHOD_ID,
            site_id=_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_returns_none_on_success() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    result = await deprecate_practice.bind(deps)(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_appends_practice_deprecated_event_from_defined() -> None:
    """Direct deprecation (no prior version)."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    await deprecate_practice.bind(deps)(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Practice", practice_id)
    assert version == 2
    assert [e.event_type for e in events] == ["PracticeDefined", "PracticeDeprecated"]
    deprecated = events[1]
    assert deprecated.event_id == _VERSIONED_EVENT_ID  # next id (versioned slot skipped)
    assert deprecated.metadata == {"command": "DeprecatePractice"}


@pytest.mark.unit
async def test_handler_appends_practice_deprecated_event_from_versioned() -> None:
    """Full lifecycle: define → version → deprecate."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    await version_practice.bind(deps)(
        VersionPractice(practice_id=practice_id, version_tag="v2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_practice.bind(deps)(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Practice", practice_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "PracticeDefined",
        "PracticeVersioned",
        "PracticeDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == _DEPRECATED_EVENT_ID


@pytest.mark.unit
async def test_handler_raises_practice_not_found_when_practice_does_not_exist() -> None:
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID], now=_NOW
    )
    handler = deprecate_practice.bind(deps)

    with pytest.raises(PracticeNotFoundError):
        await handler(
            DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=_PRACTICE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    handler = deprecate_practice.bind(deps)
    await handler(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(PracticeCannotDeprecateError):
        await handler(
            DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    deny_deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
        deny=True,
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await deprecate_practice.bind(deny_deps)(
            DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID],
        now=_NOW,
        event_store=store,
    )
    practice_id = await _define_practice_helper(deps)

    await deprecate_practice.bind(deps)(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Practice", practice_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
def test_wire_recipe_includes_deprecate_practice() -> None:
    deps = build_deps(
        ids=[_PRACTICE_ID, _DEFINED_EVENT_ID, _VERSIONED_EVENT_ID, _DEPRECATED_EVENT_ID], now=_NOW
    )
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.deprecate_practice)
