"""Unit tests for the `version_recipe` application handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.recipe import UnauthorizedError
from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeBindingReferencesUnknownParameterError,
    RecipeDefined,
    RecipeNotFoundError,
    RecipeSetpointStep,
    event_type_name,
    to_payload,
)
from cora.recipe.features import version_recipe
from cora.recipe.features.version_recipe import VersionRecipe
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000c0d4")
_RECIPE_ID = UUID("01900000-0000-7000-8000-00000000ab20")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000ab21")


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
                event_id=UUID("01900000-0000-7000-8000-00000000ab22"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _build_seeded_deps(*, deny: bool = False) -> tuple[InMemoryEventStore, Kernel]:
    store = InMemoryEventStore()
    await seed_capability(store, _CAPABILITY_ID)
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store, deny=deny)
    return store, deps


@pytest.mark.unit
async def test_handler_appends_recipe_versioned_event() -> None:
    store, deps = await _build_seeded_deps()
    handler = version_recipe.bind(deps)

    await handler(
        VersionRecipe(
            recipe_id=_RECIPE_ID,
            version_tag="v1",
            steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Recipe", _RECIPE_ID)
    assert version == 2
    assert events[1].event_type == "RecipeVersioned"
    assert events[1].payload["version_tag"] == "v1"


@pytest.mark.unit
async def test_handler_persists_closing_steps_on_the_new_version() -> None:
    store, deps = await _build_seeded_deps()
    handler = version_recipe.bind(deps)

    await handler(
        VersionRecipe(
            recipe_id=_RECIPE_ID,
            version_tag="v1",
            steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
            closing_steps=(RecipeSetpointStep(address="dev:shutter", value=0.0),),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Recipe", _RECIPE_ID)
    assert events[1].payload["closing"]["steps"] == [
        {"kind": "setpoint", "address": "dev:shutter", "value": 0.0, "verify": False}
    ]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    _, deps = await _build_seeded_deps(deny=True)
    handler = version_recipe.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            VersionRecipe(
                recipe_id=_RECIPE_ID,
                version_tag="v1",
                steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_not_found_when_recipe_stream_empty() -> None:
    store = InMemoryEventStore()
    await seed_capability(store, _CAPABILITY_ID)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = version_recipe.bind(deps)

    with pytest.raises(RecipeNotFoundError):
        await handler(
            VersionRecipe(
                recipe_id=_RECIPE_ID,
                version_tag="v1",
                steps=(RecipeSetpointStep(address="dev:x", value=2.0),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_re_validates_binding_refs_against_capability_schema() -> None:
    """Anti-hook 5: BindingRef integrity re-fires at version_recipe.

    Mirrors `test_handler_raises_binding_unknown_parameter_when_schema_missing_key` from
    define_recipe but at version time. Closes the operator-side half of the
    Capability-re-version race.
    """
    from cora.recipe.aggregates.capability import (
        CapabilityCode,
        CapabilityDefined,
        CapabilityName,
        ExecutorShape,
    )
    from cora.recipe.aggregates.capability import event_type_name as cap_event_type_name
    from cora.recipe.aggregates.capability import to_payload as cap_to_payload

    store = InMemoryEventStore()
    cap_event = CapabilityDefined(
        capability_id=_CAPABILITY_ID,
        code=CapabilityCode("cora.capability.test").value,
        name=CapabilityName("TestCapability").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        parameters_schema={"type": "object", "properties": {"angle": {"type": "number"}}},
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Capability",
        stream_id=_CAPABILITY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=cap_event_type_name(cap_event),
                payload=cap_to_payload(cap_event),
                occurred_at=cap_event.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000c0d5"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    await _seed_recipe(store)
    deps = build_deps(ids=[_EVENT_ID], now=_NOW, event_store=store)
    handler = version_recipe.bind(deps)

    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        await handler(
            VersionRecipe(
                recipe_id=_RECIPE_ID,
                version_tag="v2",
                steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("enrgy")),),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # A bad ref in closing_steps alone (main steps are valid) must ALSO
    # raise -- proving the handler validates the CONCATENATED walk.
    with pytest.raises(RecipeBindingReferencesUnknownParameterError):
        await handler(
            VersionRecipe(
                recipe_id=_RECIPE_ID,
                version_tag="v2",
                steps=(RecipeSetpointStep(address="dev:x", value=BindingRef("angle")),),
                closing_steps=(
                    RecipeSetpointStep(address="dev:shutter", value=BindingRef("enrgy")),
                ),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
