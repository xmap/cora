"""Unit tests for the `register_procedure_from_recipe` slice's pure decider."""

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.operation._recipe_expansion import canonical_json_bytes, expand, steps_to_wire
from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    InvalidProcedureIterationCapError,
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
def test_decide_hashes_closing_steps_into_the_same_steps_hash_pin() -> None:
    """A recipe whose only difference is closing_steps must hash differently
    (one combined pin, no aliasing) -- proves closing_steps actually reaches
    the hash, not just step_count."""
    cap = _capability()
    plain = _recipe(cap.id)
    with_closing = Recipe(
        id=plain.id,
        name=plain.name,
        capability_id=plain.capability_id,
        steps=plain.steps,
        status=plain.status,
        closing_steps=(RecipeSetpointStep(address="dev:shutter", value=0.0),),
    )

    plain_events = decide(
        state=None,
        command=_cmd(plain.id),
        recipe=plain,
        capability=cap,
        expansion_port=InMemoryRecipeExpander(),
        now=_NOW,
        new_id=uuid4(),
    )
    closing_events = decide(
        state=None,
        command=_cmd(with_closing.id),
        recipe=with_closing,
        capability=cap,
        expansion_port=InMemoryRecipeExpander(),
        now=_NOW,
        new_id=uuid4(),
    )
    plain_prov = plain_events[1]
    closing_prov = closing_events[1]
    assert isinstance(plain_prov, RecipeExpansionRecorded)
    assert isinstance(closing_prov, RecipeExpansionRecorded)
    assert plain_prov.steps_hash != closing_prov.steps_hash
    assert closing_prov.step_count == 2  # 1 main + 1 closing


@pytest.mark.unit
def test_decide_empty_closing_steps_hashes_identically_to_no_closing_field() -> None:
    """The migration-claim precedent applied to closing_steps: an empty
    closing list must hash EXACTLY like a recipe that never had the field,
    so no existing pinned expansion is invalidated by this feature."""
    cap = _capability()
    recipe = _recipe(cap.id)
    assert recipe.closing_steps == ()

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
    expanded = InMemoryRecipeExpander().expand(recipe.steps, {})
    legacy_hash = hashlib.sha256(canonical_json_bytes(steps_to_wire(expanded))).hexdigest()
    assert prov.steps_hash == legacy_hash


@pytest.mark.unit
def test_decide_raises_overflow_when_combined_count_exceeds_cap() -> None:
    """Overflow must range over steps + closing_steps combined, not steps alone."""
    cap = _capability()
    recipe = Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=cap.id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        closing_steps=(RecipeSetpointStep(address="dev:shutter", value=0.0),),
    )

    class _FakeSplitOverflowPort:
        version = "v1"

        def expand(
            self,
            steps: tuple[RecipeStep, ...],
            bindings: Mapping[str, Any],
        ) -> tuple[Step, ...]:
            _ = bindings
            from cora.operation.conductor import SetpointStep

            # Main list alone is well under cap; closing list alone pushes
            # the COMBINED count over it.
            first = steps[0] if steps else None
            is_main = (
                len(steps) == 1
                and isinstance(first, RecipeSetpointStep)
                and first.address == "dev:x"
            )
            size = 5 if is_main else 10_000
            return tuple(SetpointStep(address=f"x:{i}", value=i) for i in range(size))

    with pytest.raises(RecipeExpansionOverflowError) as exc:
        decide(
            state=None,
            command=_cmd(recipe.id),
            recipe=recipe,
            capability=cap,
            expansion_port=_FakeSplitOverflowPort(),  # type: ignore[arg-type]
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc.value.step_count == 10_005
    assert exc.value.cap == 10_000


@pytest.mark.unit
def test_decide_raises_determinism_error_on_closing_steps_divergence() -> None:
    """A port that diverges only on the closing-list expansion must still
    trip the determinism gate, not just a main-list divergence."""
    cap = _capability()
    recipe = Recipe(
        id=uuid4(),
        name=RecipeName("R"),
        capability_id=cap.id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        closing_steps=(RecipeSetpointStep(address="dev:shutter", value=0.0),),
    )

    class _FakeNonDeterministicClosingPort:
        version = "v1"
        _calls = 0

        def expand(
            self,
            steps: tuple[RecipeStep, ...],
            bindings: Mapping[str, Any],
        ) -> tuple[Step, ...]:
            from cora.operation.conductor import SetpointStep

            first = steps[0] if steps else None
            if (
                len(steps) == 1
                and isinstance(first, RecipeSetpointStep)
                and first.address == "dev:shutter"
            ):
                self._calls += 1
                return (SetpointStep(address="dev:shutter", value=float(self._calls)),)
            return expand(steps, bindings)

    with pytest.raises(RecipeExpansionDeterminismError):
        decide(
            state=None,
            command=_cmd(recipe.id),
            recipe=recipe,
            capability=cap,
            expansion_port=_FakeNonDeterministicClosingPort(),  # type: ignore[arg-type]
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_records_patience_cap_on_event() -> None:
    cap = _capability()
    recipe = _recipe(cap.id)
    cmd = RegisterProcedureFromRecipe(
        name="P",
        kind="center_alignment",
        target_asset_ids=(),
        parent_run_id=None,
        recipe_id=recipe.id,
        bindings={},
        max_consecutive_unconverged_iterations=4,
    )
    events = decide(
        state=None,
        command=cmd,
        recipe=recipe,
        capability=cap,
        expansion_port=InMemoryRecipeExpander(),
        now=_NOW,
        new_id=uuid4(),
    )
    reg = events[0]
    assert isinstance(reg, ProcedureRegistered)
    assert reg.max_consecutive_unconverged_iterations == 4


@pytest.mark.unit
def test_decide_rejects_patience_cap_below_one() -> None:
    cap = _capability()
    recipe = _recipe(cap.id)
    cmd = RegisterProcedureFromRecipe(
        name="P",
        kind="center_alignment",
        target_asset_ids=(),
        parent_run_id=None,
        recipe_id=recipe.id,
        bindings={},
        max_consecutive_unconverged_iterations=0,
    )
    with pytest.raises(InvalidProcedureIterationCapError):
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
            # Overflow is isolated to the main list; an empty input (the
            # closing_steps call, since big_recipe has none) must expand to
            # empty, or the combined count double-counts a fixed-size fake.
            _ = bindings
            if not steps:
                return ()
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
