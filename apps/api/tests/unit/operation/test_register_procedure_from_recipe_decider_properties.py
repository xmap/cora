"""Property-based tests for `register_procedure_from_recipe.decide`.

Complements the example-based
`test_register_procedure_from_recipe_decider.py` with universal claims
across generated inputs. The slice is a bespoke genesis with recipe
expansion that emits a 2-event block
`[ProcedureRegistered, RecipeExpansionRecorded]`. The full
capability / recipe-expansion gate matrix (executor-shape mismatch,
invalid bindings, overflow, determinism) is pinned by the example
tests; the PBT asserts only the claims that hold across the whole input
space:

  - Any non-None state always raises `ProcedureAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command /
    source aggregates / clock / new_id.
  - On the happy path (fresh stream, PROCEDURE-shaped Capability,
    no parameters_schema, 1-step Recipe) the emitted block threads the
    injected fields: both events carry occurred_at=now, the genesis
    event carries procedure_id=new_id with recipe_id / capability_id
    sourced from the input aggregates, and the provenance event carries
    procedure_id=new_id with recipe_id / capability_id likewise sourced.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.operation.adapters.in_memory_recipe_expander import (
    InMemoryRecipeExpander,
)
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureName,
    ProcedureRegistered,
    ProcedureStatus,
    RecipeExpansionRecorded,
)
from cora.operation.features.register_procedure_from_recipe import (
    RegisterProcedureFromRecipe,
    decide,
)
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    CapabilityStatus,
    ExecutorShape,
)
from cora.recipe.aggregates.recipe import (
    Recipe,
    RecipeName,
    RecipeSetpointStep,
    RecipeStatus,
)
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = printable_ascii_text(min_size=1, max_size=200)
_KIND = printable_ascii_text(min_size=1, max_size=50)


def _capability(capability_id: UUID) -> Capability:
    return Capability(
        id=capability_id,
        code=CapabilityCode("cora.capability.test"),
        name=CapabilityName("Test"),
        status=CapabilityStatus.DEFINED,
        executor_shapes=frozenset({ExecutorShape.PROCEDURE}),
        parameters_schema=None,
    )


def _recipe(recipe_id: UUID, capability_id: UUID) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=RecipeName("R"),
        capability_id=capability_id,
        steps=(RecipeSetpointStep(address="dev:x", value=1.0),),
        status=RecipeStatus.DEFINED,
    )


def _command(*, name: str, kind: str, recipe_id: UUID) -> RegisterProcedureFromRecipe:
    return RegisterProcedureFromRecipe(
        name=name,
        kind=kind,
        target_asset_ids=(),
        parent_run_id=None,
        recipe_id=recipe_id,
        bindings={},
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    existing_status=st.sampled_from(list(ProcedureStatus)),
    name=_NAME,
    kind=_KIND,
    recipe_id=st.uuids(),
    capability_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    existing_status: ProcedureStatus,
    name: str,
    kind: str,
    recipe_id: UUID,
    capability_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises ProcedureAlreadyExistsError carrying state.id."""
    existing = Procedure(
        id=existing_id,
        name=ProcedureName("prior"),
        kind="K",
        target_asset_ids=frozenset(),
        status=existing_status,
        parent_run_id=None,
        activity_logbook_id=None,
    )
    with pytest.raises(ProcedureAlreadyExistsError) as exc:
        decide(
            state=existing,
            command=_command(name=name, kind=kind, recipe_id=recipe_id),
            recipe=_recipe(recipe_id, capability_id),
            capability=_capability(capability_id),
            expansion_port=InMemoryRecipeExpander(),
            now=now,
            new_id=new_id,
        )
    assert exc.value.procedure_id == existing_id


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    recipe_id=st.uuids(),
    capability_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_happy_path_threads_injected_ids_and_clock(
    name: str,
    kind: str,
    recipe_id: UUID,
    capability_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """The genesis block threads new_id + now and sources recipe / capability ids."""
    events = decide(
        state=None,
        command=_command(name=name, kind=kind, recipe_id=recipe_id),
        recipe=_recipe(recipe_id, capability_id),
        capability=_capability(capability_id),
        expansion_port=InMemoryRecipeExpander(),
        now=now,
        new_id=new_id,
    )
    assert len(events) == 2
    registered, provenance = events
    assert isinstance(registered, ProcedureRegistered)
    assert registered.procedure_id == new_id
    assert registered.recipe_id == recipe_id
    assert registered.capability_id == capability_id
    assert registered.occurred_at == now
    assert isinstance(provenance, RecipeExpansionRecorded)
    assert provenance.procedure_id == new_id
    assert provenance.recipe_id == recipe_id
    assert provenance.capability_id == capability_id
    assert provenance.occurred_at == now


@pytest.mark.unit
@given(
    name=_NAME,
    kind=_KIND,
    recipe_id=st.uuids(),
    capability_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    name: str,
    kind: str,
    recipe_id: UUID,
    capability_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal results (no clock/id leakage)."""
    command = _command(name=name, kind=kind, recipe_id=recipe_id)
    recipe = _recipe(recipe_id, capability_id)
    capability = _capability(capability_id)
    first = decide(
        state=None,
        command=command,
        recipe=recipe,
        capability=capability,
        expansion_port=InMemoryRecipeExpander(),
        now=now,
        new_id=new_id,
    )
    second = decide(
        state=None,
        command=command,
        recipe=recipe,
        capability=capability,
        expansion_port=InMemoryRecipeExpander(),
        now=now,
        new_id=new_id,
    )
    assert first == second
