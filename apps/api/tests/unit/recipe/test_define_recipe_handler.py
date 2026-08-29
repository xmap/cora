"""Unit tests for the `define_recipe` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.recipe import UnauthorizedError
from cora.recipe.aggregates.capability import CapabilityNotFoundError
from cora.recipe.aggregates.recipe import (
    BindingRef,
    EmptyRecipeStepsError,
    RecipeBindingReferencesUnknownParameterError,
    RecipeSetpointStep,
)
from cora.recipe.features import define_recipe
from cora.recipe.features.define_recipe import DefineRecipe
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ab10")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab11")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c0d2")


async def _seed_capability_with_schema(
    store: InMemoryEventStore,
    capability_id: UUID,
    *,
    parameters_schema: dict[str, object] | None = None,
) -> None:
    """Seed a Capability stream directly to carry parameters_schema (the
    `seed_capability` helper does not expose this field)."""
    from cora.infrastructure.event_envelope import to_new_event
    from cora.recipe.aggregates.capability import (
        CapabilityCode,
        CapabilityDefined,
        CapabilityName,
        ExecutorShape,
        event_type_name,
        to_payload,
    )

    event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.test").value,
        name=CapabilityName("TestCapability").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        parameters_schema=parameters_schema,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000c0d3"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _build_seeded_deps(
    *,
    ids: list[UUID] | None = None,
    deny: bool = False,
    parameters_schema: dict[str, object] | None = None,
) -> tuple[InMemoryEventStore, Kernel]:
    store = InMemoryEventStore()
    if parameters_schema is not None:
        await _seed_capability_with_schema(
            store, _CAPABILITY_ID, parameters_schema=parameters_schema
        )
    else:
        await seed_capability(store, _CAPABILITY_ID)
    deps = build_deps(ids=ids or [_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=deny)
    return store, deps


@pytest.mark.unit
async def test_handler_returns_generated_recipe_id() -> None:
    _, deps = await _build_seeded_deps()
    handler = define_recipe.bind(deps)

    result = await handler(
        DefineRecipe(
            name="R",
            capability_id=_CAPABILITY_ID,
            steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_recipe_defined_event_to_store() -> None:
    store, deps = await _build_seeded_deps()
    handler = define_recipe.bind(deps)

    await handler(
        DefineRecipe(
            name="R",
            capability_id=_CAPABILITY_ID,
            steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Recipe", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RecipeDefined"
    assert stored.payload["recipe_id"] == str(_NEW_ID)
    assert stored.payload["capability_id"] == str(_CAPABILITY_ID)


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    _, deps = await _build_seeded_deps(deny=True)
    handler = define_recipe.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DefineRecipe(
                name="R",
                capability_id=_CAPABILITY_ID,
                steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_stream_missing() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = define_recipe.bind(deps)

    bogus = UUID("01900000-0000-7000-8000-deadbeefcafe")
    with pytest.raises(CapabilityNotFoundError):
        await handler(
            DefineRecipe(
                name="R",
                capability_id=bogus,
                steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    recipe_events, version = await store.load("Recipe", _NEW_ID)
    assert recipe_events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_raises_binding_unknown_parameter_when_schema_missing_key() -> None:
    """BindingRef integrity validator fires before decider on Capability load."""
    _, deps = await _build_seeded_deps(
        parameters_schema={"type": "object", "properties": {"angle": {"type": "number"}}}
    )
    handler = define_recipe.bind(deps)

    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        await handler(
            DefineRecipe(
                name="R",
                capability_id=_CAPABILITY_ID,
                steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("enrgy")),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_binding_unknown_parameter_for_a_bad_ref_in_closing_steps() -> None:
    """A bad BindingRef in closing_steps must be caught too, not just in steps
    -- proving the handler validates the CONCATENATED walk, not steps alone."""
    _, deps = await _build_seeded_deps(
        parameters_schema={"type": "object", "properties": {"angle": {"type": "number"}}}
    )
    handler = define_recipe.bind(deps)

    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        await handler(
            DefineRecipe(
                name="R",
                capability_id=_CAPABILITY_ID,
                steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),),
                closing_steps=(
                    RecipeSetpointStep(address="dev:shutter", value=BindingRef("enrgy")),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_persists_closing_steps_on_the_recipe() -> None:
    store, deps = await _build_seeded_deps()
    handler = define_recipe.bind(deps)

    recipe_id = await handler(
        DefineRecipe(
            name="R",
            capability_id=_CAPABILITY_ID,
            steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
            closing_steps=(RecipeSetpointStep(address="dev:shutter", value=0.0),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert recipe_id == _NEW_ID
    recipe_events, _ = await store.load("Recipe", _NEW_ID)
    assert recipe_events[0].payload["closing"]["steps"] == [
        {"kind": "setpoint", "address": "dev:shutter", "value": 0.0, "verify": False}
    ]


@pytest.mark.unit
async def test_handler_raises_empty_recipe_steps_when_command_steps_empty() -> None:
    _, deps = await _build_seeded_deps()
    handler = define_recipe.bind(deps)

    with pytest.raises(EmptyRecipeStepsError):
        await handler(
            DefineRecipe(name="R", capability_id=_CAPABILITY_ID, steps=()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
