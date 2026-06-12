"""Unit tests for the `register_procedure_from_recipe` slice's pure decider."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.operation._recipe_expansion import expand
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    InvalidRecipeBindingsError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStatus,
    RecipeExpansionDeterminismError,
    RecipeExpansionOverflowError,
    RecipeExpansionRecorded,
)
from cora.operation.conductor import Step
from cora.operation.features.register_procedure_from_recipe import (
    RegisterProcedureFromRecipe,
    decide,
)
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
)
from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeName,
    RecipeSetpointStep,
    RecipeStatus,
    RecipeStep,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _capability(
    *,
    shapes: frozenset[ExecutorShape] | None = None,
    parameters_schema: dict[str, object] | None = None,
) -> Capability:
    return Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.test"),
        name=CapabilityName("Test"),
        status=__import__(
            "cora.recipe.aggregates.capability", fromlist=["CapabilityStatus"]
        ).CapabilityStatus.DEFINED,
        executor_shapes=shapes or frozenset({ExecutorShape.PROCEDURE}),
        parameters_schema=parameters_schema,
    )


def _recipe(capability_id: UUID) -> Recipe:
    return Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=capability_id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=RecipeStatus.DEFINED,
    )


def _cmd(recipe_id: UUID) -> RegisterProcedureFromRecipe:
    return RegisterProcedureFromRecipe(
        name="P",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        recipe_id=recipe_id,
        bindings={},
    )


@pytest.mark.unit
def test_decide_emits_registered_plus_recipe_expansion_recorded() -> None:
    cap = _capability()
    recipe = _recipe(cap.id)
    new_id = uuid4()
    events = decide(
        state=None,
        command=_cmd(recipe.id),
        recipe=recipe,
        capability=cap,
        expansion_port=InMemoryRecipeExpander(),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 2
    reg, prov = events
    assert isinstance(reg, ProcedureRegistered)
    assert reg.procedure_id == new_id
    assert reg.recipe_id == recipe.id
    assert reg.capability_id == cap.id
    assert isinstance(prov, RecipeExpansionRecorded)
    assert prov.recipe_id == recipe.id
    assert prov.capability_id == cap.id
    assert prov.expansion_port_version == "v2-pseudoaxis-aware"
    assert prov.step_count == 1


@pytest.mark.unit
def test_decide_raises_already_exists_when_state_present() -> None:
    cap = _capability()
    recipe = _recipe(cap.id)
    existing = Procedure(
        id=uuid4(),
        name=ProcedureName("X"),
        kind="K",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
        parent_run_id=None,
        activity_logbook_id=None,
    )
    with pytest.raises(ProcedureAlreadyExistsError):
        decide(
            state=existing,
            command=_cmd(recipe.id),
            recipe=recipe,
            capability=cap,
            expansion_port=InMemoryRecipeExpander(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_executor_mismatch_when_capability_excludes_procedure() -> None:
    cap = _capability(shapes=frozenset({ExecutorShape.METHOD}))
    recipe = _recipe(cap.id)
    with pytest.raises(ProcedureCapabilityExecutorMismatchError):
        decide(
            state=None,
            command=_cmd(recipe.id),
            recipe=recipe,
            capability=cap,
            expansion_port=InMemoryRecipeExpander(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_invalid_bindings_when_values_fail_schema() -> None:
    schema: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {"angle": {"type": "number"}},
        "required": ["angle"],
    }
    cap = _capability(parameters_schema=schema)
    recipe = _recipe(cap.id)
    cmd = RegisterProcedureFromRecipe(
        name="P",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        recipe_id=recipe.id,
        bindings={"angle": "not-a-number"},
    )
    with pytest.raises(InvalidRecipeBindingsError):
        decide(
            state=None,
            command=cmd,
            recipe=recipe,
            capability=cap,
            expansion_port=InMemoryRecipeExpander(),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_raises_overflow_when_expansion_exceeds_cap() -> None:
    cap = _capability()
    big_recipe = Recipe(
        id=uuid4(),
        name=RecipeName("Big"),
        capability_id=cap.id,
        steps=tuple(RecipeSetpointStep(address=f"dev:{i}", value=float(i)) for i in range(3)),
    )

    class _FakeOverflowPort:
        version = "v1"

        def expand(
            self,
            steps: tuple[RecipeStep, ...],
            bindings: Mapping[str, Any],
        ) -> tuple[Step, ...]:
            _ = steps, bindings
            from cora.operation.conductor import SetpointStep

            return tuple(SetpointStep(address=f"x:{i}", value=i) for i in range(10_001))

    with pytest.raises(RecipeExpansionOverflowError) as exc:
        decide(
            state=None,
            command=_cmd(big_recipe.id),
            recipe=big_recipe,
            capability=cap,
            expansion_port=_FakeOverflowPort(),  # type: ignore[arg-type]
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc.value.step_count == 10_001
    assert exc.value.cap == 10_000


@pytest.mark.unit
def test_decide_raises_determinism_error_when_expansions_differ() -> None:
    cap = _capability()
    recipe = _recipe(cap.id)

    class _NonDeterministicPort:
        version = "v1"
        _calls = 0

        def expand(
            self,
            steps: tuple[RecipeStep, ...],
            bindings: Mapping[str, Any],
        ) -> tuple[Step, ...]:
            _ = steps, bindings
            self._calls += 1
            from cora.operation.conductor import SetpointStep

            return (SetpointStep(address=f"call:{self._calls}", value=1.0),)

    with pytest.raises(RecipeExpansionDeterminismError) as exc:
        decide(
            state=None,
            command=_cmd(recipe.id),
            recipe=recipe,
            capability=cap,
            expansion_port=_NonDeterministicPort(),  # type: ignore[arg-type]
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc.value.recipe_id == recipe.id


@pytest.mark.unit
def test_decide_with_real_expand_function_preserves_step_count() -> None:
    """End-to-end sanity: the default `expand` is pure + matches the 1-step Recipe."""
    cap = _capability()
    recipe = _recipe(cap.id)
    # Direct sanity check on the bridge.
    expanded = expand(recipe.steps, {})
    assert len(expanded) == 1
    # And via the decider:
    events = decide(
        state=None,
        command=_cmd(recipe.id),
        recipe=recipe,
        capability=cap,
        expansion_port=InMemoryRecipeExpander(),
        now=_NOW,
        new_id=uuid4(),
    )
    prov = events[1]
    assert isinstance(prov, RecipeExpansionRecorded)
    assert prov.step_count == 1
