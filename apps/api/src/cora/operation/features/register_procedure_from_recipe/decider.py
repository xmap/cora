"""Pure decider for the `RegisterProcedureFromRecipe` command.

Drives the Procedure's step list from a Recipe's templated `steps` +
operator-supplied parameter bindings (instead of an inline step list
per `register_procedure`). Emits a 2-event genesis block:
  - `ProcedureRegistered`: standard Procedure genesis (with `recipe_id`
                            set and `capability_id` denormalized from
                            Recipe.capability_id)
  - `RecipeExpansionRecorded`: template-invocation-grain provenance

The expanded `tuple[Step, ...]` is computed locally for the cap +
determinism validation gates but NOT persisted at v1: the provenance
event records `(recipe_id, recipe_version, capability_id,
capability_version, bindings, expansion_port_version, steps_hash,
bindings_hash, step_count)`, sufficient to re-expand deterministically
at run time. The handler loads BOTH Recipe and Capability (the Recipe
has the steps; the Capability has the parameters_schema for binding
shape validation + executor_shapes for the cross-BC guard).

Pure-function contract: `port.expand` is called TWICE here (once for
the real expansion, once for the determinism check). The port wraps a
pure function so this is cheap.

Invariants:
  - Procedure stream must be fresh (state is None)
    -> ProcedureAlreadyExistsError
  - Recipe must be present (handler raises RecipeNotFoundError first)
  - Capability must be present (handler raises CapabilityNotFoundError first)
  - Capability.executor_shapes must contain PROCEDURE
    -> ProcedureCapabilityExecutorMismatchError
  - bindings must validate against Capability.parameters_schema
    (delegates to validate_values_against_schema; STRICT-when-no-schema
    via the existing infra)
    -> InvalidRecipeBindingsError (wraps SchemaValidationError)
  - kind: 1-50 chars via the shared validate_bounded_text helper
    -> InvalidProcedureKindError
  - name: 1-200 chars via ProcedureName VO
    -> InvalidProcedureNameError
  - Expanded step count must not exceed RECIPE_EXPANSION_STEP_MAX
    -> RecipeExpansionOverflowError
  - Two consecutive expansion calls must yield identical results
    -> RecipeExpansionDeterminismError
"""

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.operation._recipe_expansion import canonical_json_bytes, steps_to_wire
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    RECIPE_EXPANSION_STEP_MAX,
    InvalidProcedureKindError,
    InvalidRecipeBindingsError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureEvent,
    ProcedureName,
    ProcedureRegistered,
    RecipeExpansionDeterminismError,
    RecipeExpansionOverflowError,
    RecipeExpansionRecorded,
)
from cora.operation.conductor import Step
from cora.operation.features.register_procedure_from_recipe.command import (
    RegisterProcedureFromRecipe,
)
from cora.operation.ports.recipe_expander import RecipeExpander
from cora.recipe.aggregates.capability import Capability, ExecutorShape
from cora.recipe.aggregates.recipe import Recipe
from cora.shared.bounded_text import validate_bounded_text
from cora.shared.json_schema_validation import validate_values_against_schema


def _hash_steps(steps: tuple[Step, ...]) -> str:
    """Content-address the expanded Step tuple per memo §RecipeExpansionRecorded.

    Hashing the expanded steps (not the unexpanded Recipe template)
    pins what the Conductor will actually execute, so a Recipe
    re-version that produces equivalent expanded steps still hashes
    identically.
    """
    return hashlib.sha256(canonical_json_bytes(steps_to_wire(steps))).hexdigest()


def _hash_bindings(bindings: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(dict(bindings))).hexdigest()


def decide(
    state: Procedure | None,
    command: RegisterProcedureFromRecipe,
    *,
    recipe: Recipe,
    capability: Capability,
    expansion_port: RecipeExpander,
    now: datetime,
    new_id: UUID,
) -> list[ProcedureEvent]:
    """Decide the genesis event block for a Recipe-driven Procedure registration.

    Returns `[ProcedureRegistered, RecipeExpansionRecorded]`. The expanded
    step tuple is computed locally for the overflow + determinism gates
    but is NOT carried out of the decider; the provenance event's
    `(recipe_id, recipe_version, capability_id, capability_version,
    bindings, expansion_port_version, steps_hash, bindings_hash,
    step_count)` are sufficient for deterministic re-expansion.
    """
    if state is not None:
        raise ProcedureAlreadyExistsError(state.id)
    if ExecutorShape.PROCEDURE not in capability.executor_shapes:
        raise ProcedureCapabilityExecutorMismatchError(new_id, capability.id)

    bindings_dict = dict(command.bindings)
    validate_values_against_schema(
        bindings_dict,
        capability.parameters_schema,
        error_class=InvalidRecipeBindingsError,
    )

    kind = validate_bounded_text(
        command.kind,
        max_length=PROCEDURE_KIND_MAX_LENGTH,
        error_class=InvalidProcedureKindError,
    )
    name = ProcedureName(command.name)

    steps_first = expansion_port.expand(recipe.steps, bindings_dict)
    if len(steps_first) > RECIPE_EXPANSION_STEP_MAX:
        raise RecipeExpansionOverflowError(
            step_count=len(steps_first), cap=RECIPE_EXPANSION_STEP_MAX
        )

    # Determinism check: re-expand and compare. The port wraps a pure
    # function; any divergence is a server-side bug in the port or the
    # recipe body.
    steps_second = expansion_port.expand(recipe.steps, bindings_dict)
    if steps_first != steps_second:
        raise RecipeExpansionDeterminismError(recipe.id)

    return [
        ProcedureRegistered(
            procedure_id=new_id,
            name=name.value,
            kind=kind,
            target_asset_ids=tuple(command.target_asset_ids),
            parent_run_id=command.parent_run_id,
            capability_id=recipe.capability_id,
            recipe_id=recipe.id,
            occurred_at=now,
        ),
        RecipeExpansionRecorded(
            procedure_id=new_id,
            recipe_id=recipe.id,
            recipe_version=recipe.version,
            capability_id=capability.id,
            capability_version=capability.version,
            bindings=bindings_dict,
            expansion_port_version=expansion_port.version,
            steps_hash=_hash_steps(steps_first),
            bindings_hash=_hash_bindings(bindings_dict),
            step_count=len(steps_first),
            occurred_at=now,
        ),
    ]
