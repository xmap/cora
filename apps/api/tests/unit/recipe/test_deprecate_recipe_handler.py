"""Unit tests for the `deprecate_recipe` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.recipe import UnauthorizedError
from cora.recipe.aggregates.recipe import (
    RecipeDefined,
    RecipeNotFoundError,
    RecipeSetpointStep,
    event_type_name,
    to_payload,
)
from cora.recipe.features import deprecate_recipe
from cora.recipe.features.deprecate_recipe import DeprecateRecipe
from cora.shared.deprecation import DeprecationReason
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_RECIPE_ID = UUID("01900000-0000-7000-8000-00000000ab30")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab31")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c0e0")


async def _seed_recipe(store: InMemoryEventStore) -> None:
    event = RecipeDefined(
        recipe_id=_RECIPE_ID,
        name="R",
        capability_id=_CAPABILITY_ID,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Recipe",
        stream_id=_RECIPE_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000ab32"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_handler_appends_recipe_deprecated_event() -> None:
    store = InMemoryEventStore()
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = deprecate_recipe.bind(deps)

    await handler(
        DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=_RECIPE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Recipe", _RECIPE_ID)
    assert version == 2
    assert events[1].event_type == "RecipeDeprecated"


@pytest.mark.unit
async def test_handler_passes_through_replaced_by_recipe_id() -> None:
    store = InMemoryEventStore()
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = deprecate_recipe.bind(deps)

    successor = UUID("01900000-0000-7000-8000-aceaceaceace")
    await handler(
        DeprecateRecipe(
            reason=DeprecationReason.SUPERSEDED,
            recipe_id=_RECIPE_ID,
            replaced_by_recipe_id=successor,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Recipe", _RECIPE_ID)
    assert events[1].payload["replaced_by_recipe_id"] == str(successor)


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = deprecate_recipe.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=_RECIPE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_not_found_when_recipe_stream_empty() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = deprecate_recipe.bind(deps)

    with pytest.raises(RecipeNotFoundError):
        await handler(
            DeprecateRecipe(reason=DeprecationReason.SUPERSEDED, recipe_id=_RECIPE_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
