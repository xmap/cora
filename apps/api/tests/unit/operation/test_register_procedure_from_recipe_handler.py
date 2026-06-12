"""Unit tests for the `register_procedure_from_recipe` application handler.

Covers the load-Recipe + load-Capability cross-aggregate fan-out plus
the BindingRef-stale guard (anti-hook 5 expansion-time half).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    RecipeBindingsStaleAgainstCurrentCapabilityError,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features import register_procedure_from_recipe
from cora.operation.features.register_procedure_from_recipe import (
    RegisterProcedureFromRecipe,
)
from cora.recipe.aggregates.capability import CapabilityNotFoundError
from cora.recipe.aggregates.recipe import (
    BindingRef,
    RecipeDefined,
    RecipeNotFoundError,
    RecipeSetpointStep,
    event_type_name,
    to_payload,
)
from tests.unit._helpers import build_deps, seed_capability

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NEW_ID = UUID("01900000-0000-7000-8000-00000000ad01")
_EVENT_ID_A = UUID("01900000-0000-7000-8000-00000000ad02")
_EVENT_ID_B = UUID("01900000-0000-7000-8000-00000000ad03")
_RECIPE_ID = UUID("01900000-0000-7000-8000-00000000af01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-00000000af02")


async def _seed_capability_with_schema(
    store: InMemoryEventStore,
    capability_id: UUID,
    schema: dict[str, object] | None,
) -> None:
    """Seed a Capability with an explicit parameters_schema (the shared
    helper does not expose this kwarg)."""
    from cora.recipe.aggregates.capability import (
        CapabilityCode,
        CapabilityDefined,
        CapabilityName,
        ExecutorShape,
    )
    from cora.recipe.aggregates.capability import event_type_name as cap_etn
    from cora.recipe.aggregates.capability import to_payload as cap_tp

    cap_event = CapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.test").value,
        name=CapabilityName("Test").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        parameters_schema=schema,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Capability",
        stream_id=capability_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=cap_etn(cap_event),
                payload=cap_tp(cap_event),
                occurred_at=_NOW,
                event_id=UUID("01900000-0000-7000-8000-00000000af03"),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _seed_recipe(
    store: InMemoryEventStore,
    recipe_id: UUID,
    capability_id: UUID,
    *,
    with_binding: bool = False,
) -> None:
    steps = (
        RecipeSetpointStep(
            address="dev:x",
            value=BindingRef("angle") if with_binding else 1.0,
        ),
    )
    event = RecipeDefined(
        recipe_id=recipe_id,
        name="R",
        capability_id=capability_id,
        steps=steps,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Recipe",
        stream_id=recipe_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=UUID("01900000-0000-7000-8000-00000000af04"),
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
    await _seed_recipe(store, _RECIPE_ID, _CAPABILITY_ID)
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID_A, _EVENT_ID_B],
        now=_NOW,
        event_store=store,
        deny=deny,
    )
    return store, deps


@pytest.mark.unit
async def test_handler_returns_generated_procedure_id() -> None:
    store, deps = await _build_seeded_deps()
    handler = register_procedure_from_recipe.bind(deps, expansion_port=InMemoryRecipeExpander())

    result = await handler(
        RegisterProcedureFromRecipe(
            name="P",
            kind="bakeout",
            target_asset_ids=(),
            parent_run_id=None,
            recipe_id=_RECIPE_ID,
            bindings={},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID

    events, version = await store.load("Procedure", _NEW_ID)
    assert version == 2
    assert events[0].event_type == "ProcedureRegistered"
    assert events[0].payload["recipe_id"] == str(_RECIPE_ID)
    assert events[0].payload["capability_id"] == str(_CAPABILITY_ID)
    assert events[1].event_type == "RecipeExpansionRecorded"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    _, deps = await _build_seeded_deps(deny=True)
    handler = register_procedure_from_recipe.bind(deps, expansion_port=InMemoryRecipeExpander())
    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterProcedureFromRecipe(
                name="P",
                kind="bakeout",
                target_asset_ids=(),
                parent_run_id=None,
                recipe_id=_RECIPE_ID,
                bindings={},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_recipe_not_found_when_stream_missing() -> None:
    store = InMemoryEventStore()
    await seed_capability(store, _CAPABILITY_ID)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID_A], now=_NOW, event_store=store)
    handler = register_procedure_from_recipe.bind(deps, expansion_port=InMemoryRecipeExpander())
    with pytest.raises(RecipeNotFoundError):
        await handler(
            RegisterProcedureFromRecipe(
                name="P",
                kind="bakeout",
                target_asset_ids=(),
                parent_run_id=None,
                recipe_id=_RECIPE_ID,
                bindings={},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_capability_not_found_when_recipe_points_at_missing() -> None:
    """Recipe exists but its capability_id has no Capability stream."""
    store = InMemoryEventStore()
    await _seed_recipe(store, _RECIPE_ID, _CAPABILITY_ID)
    # Note: NO seed_capability call.
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID_A], now=_NOW, event_store=store)
    handler = register_procedure_from_recipe.bind(deps, expansion_port=InMemoryRecipeExpander())
    with pytest.raises(CapabilityNotFoundError):
        await handler(
            RegisterProcedureFromRecipe(
                name="P",
                kind="bakeout",
                target_asset_ids=(),
                parent_run_id=None,
                recipe_id=_RECIPE_ID,
                bindings={},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_when_capability_schema_drifted_since_recipe_write() -> None:
    """Anti-hook 5 expansion-time half: Capability was re-versioned to drop
    a parameter the Recipe binds; handler rejects with
    RecipeBindingsStaleAgainstCurrentCapabilityError."""
    store = InMemoryEventStore()
    # Capability with NO `angle` parameter (the Recipe's binding name)
    await _seed_capability_with_schema(
        store,
        _CAPABILITY_ID,
        schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"energy": {"type": "number"}},
        },
    )
    # Recipe binds an `angle` BindingRef that no longer resolves.
    await _seed_recipe(store, _RECIPE_ID, _CAPABILITY_ID, with_binding=True)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID_A], now=_NOW, event_store=store)
    handler = register_procedure_from_recipe.bind(deps, expansion_port=InMemoryRecipeExpander())
    with pytest.raises(RecipeBindingsStaleAgainstCurrentCapabilityError) as exc:
        await handler(
            RegisterProcedureFromRecipe(
                name="P",
                kind="bakeout",
                target_asset_ids=(),
                parent_run_id=None,
                recipe_id=_RECIPE_ID,
                bindings={"angle": 30.0},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert "angle" in exc.value.missing_binding_names
    procs, version = await store.load("Procedure", _NEW_ID)
    assert procs == []
    assert version == 0
