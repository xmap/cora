"""Pure `expand` for Recipe step tuples -> Conductor `Step` lists.

Cross-BC bridge: the Recipe BC's `RecipeStep` union + `BindingRef`
sentinel describe parameterized scan recipes; the Operation BC's `Step`
union (the arms are pinned against the Procedure aggregate's
`STEP_KIND_VALUES`) is what the Conductor walks. The direction
Operation -> Recipe is the allowed dependency edge (tach-enforced), so
this expansion bridge lives here.

Per [[project-recipe-aggregate-design]] the expansion contract is
pure: no clock, no port I/O, no randomness, no module-global state.
Same inputs `(steps, bindings)` yield identical outputs. The
`register_procedure_from_recipe` slice re-runs `expand` once at
validation time and compares results to enforce determinism via the
`RecipeExpansionDeterminismError` rejection.
"""

from collections.abc import Mapping
from typing import Any

from cora.operation.conductor import (
    ActionStep,
    CaptureStep,
    CheckStep,
    ComputeStep,
    EqualsCriterion,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
)
from cora.recipe.aggregates.recipe import (
    RecipeActionStep,
    RecipeCaptureStep,
    RecipeComputeStep,
    RecipeSetpointStep,
    RecipeStep,
)
from cora.recipe.aggregates.recipe.body import CaptureRef, resolve_value
from cora.shared.canonical_json import canonical_json_bytes

_CAPTURE_WIRE_KEY = "__capture__"
"""Stable sentinel key for a `CaptureRef` in the expanded-steps hash form.

A `CaptureRef` survives `expand` (unlike `BindingRef`, which `resolve_value`
substitutes away), so the hash serializer must encode it deterministically.
This serializer's hash is compared only against itself (re-expand vs the
pinned `steps_hash`), so the key need only be internally stable; it mirrors
the Recipe BC / Conductor `__capture__` sentinel for readability."""


def _criterion_from_wire(
    payload: Mapping[str, Any],
) -> EqualsCriterion | WithinToleranceCriterion:
    """Translate a `RecipeCheckStep.criterion` wire dict to the typed union.

    Mirrors the Conductor's `_criterion_to_dict` serialization shape
    arm-for-arm. Extension: a new criterion kind lands in three places:
    the Conductor's `_criterion_to_dict` / `_criterion_matches` arms,
    this function's arms, and the matching test in
    `test_recipe_step_variants_match_step_union`.
    """
    kind = payload["kind"]
    if kind == "equals":
        return EqualsCriterion(expected=payload["expected"])
    if kind == "within_tolerance":
        return WithinToleranceCriterion(
            expected=payload["expected"], tolerance=payload["tolerance"]
        )
    msg = f"unknown criterion kind: {kind!r}"
    raise ValueError(msg)


def _expand_step(step: RecipeStep, bindings: Mapping[str, Any]) -> Step:
    """Expand one recipe step into a concrete `Step` per the union arm."""
    if isinstance(step, RecipeSetpointStep):
        return SetpointStep(
            address=step.address,
            value=resolve_value(step.value, bindings),
            verify=step.verify,
        )
    if isinstance(step, RecipeActionStep):
        return ActionStep(
            name=step.name,
            params={key: resolve_value(val, bindings) for key, val in step.params.items()},
        )
    if isinstance(step, RecipeCaptureStep):
        return CaptureStep(address=step.address, capture_name=step.capture_name)
    if isinstance(step, RecipeComputeStep):
        # All fields are LITERAL (no BindingRef on a compute step yet), so they
        # pass through verbatim with no resolve_value pass; `capture_name`
        # (slice 6c) is a literal template field carried through unresolved.
        # Binding a compute parameter is the deferred widening.
        return ComputeStep(
            command=step.command,
            input_uris=step.input_uris,
            output_uri=step.output_uri,
            parameters=dict(step.parameters),
            capture_name=step.capture_name,
        )
    # RecipeCheckStep: criterion is a wire-format dict (kept dict-shaped
    # in Recipe BC to avoid an Operation -> Recipe import).
    return CheckStep(
        address=step.address,
        criterion=_criterion_from_wire(step.criterion),
    )


def expand(steps: tuple[RecipeStep, ...], bindings: Mapping[str, Any]) -> tuple[Step, ...]:
    """Expand `steps` against `bindings` to a flat tuple of Conductor `Step`s.

    Pure function: same inputs yield identical outputs. Order of `steps`
    is preserved.

    Raises `UnboundRecipeBindingError` (from `cora.recipe.aggregates.recipe`)
    if any `BindingRef.name` in `steps` is missing from `bindings`. Raises
    `ValueError` for unknown criterion kinds in a `RecipeCheckStep`. Extra
    bindings (keys in `bindings` that no `BindingRef` references) are
    silently ignored.
    """
    return tuple(_expand_step(step, bindings) for step in steps)


def _criterion_to_wire(
    criterion: EqualsCriterion | WithinToleranceCriterion,
) -> dict[str, Any]:
    """Mirrors `_criterion_from_wire`: typed -> wire dict."""
    if isinstance(criterion, EqualsCriterion):
        return {"kind": "equals", "expected": criterion.expected}
    return {
        "kind": "within_tolerance",
        "expected": criterion.expected,
        "tolerance": criterion.tolerance,
    }


def _step_to_wire(step: Step) -> dict[str, Any]:
    if isinstance(step, SetpointStep):
        value: Any = (
            {_CAPTURE_WIRE_KEY: step.value.capture_name}
            if isinstance(step.value, CaptureRef)
            else step.value
        )
        return {
            "kind": "setpoint",
            "address": step.address,
            "value": value,
            "verify": step.verify,
        }
    if isinstance(step, ActionStep):
        return {
            "kind": "action",
            "name": step.name,
            "params": dict(step.params),
        }
    if isinstance(step, CaptureStep):
        return {
            "kind": "capture",
            "address": step.address,
            "capture_name": step.capture_name,
        }
    if isinstance(step, ComputeStep):
        return {
            "kind": "compute",
            "command": list(step.command),
            "input_uris": list(step.input_uris),
            "output_uri": step.output_uri,
            "parameters": dict(step.parameters),
            "capture_name": step.capture_name,
        }
    return {
        "kind": "check",
        "address": step.address,
        "criterion": _criterion_to_wire(step.criterion),
    }


def steps_to_wire(steps: tuple[Step, ...]) -> list[dict[str, Any]]:
    """Canonical list-of-dicts for hashing or persisting expanded Steps.

    Downstream re-expansion (run-time replay) reuses this serializer
    to recompute `steps_hash` from a freshly-expanded Recipe and
    confirm it matches the `RecipeExpansionRecorded.steps_hash` pin.
    """
    return [_step_to_wire(step) for step in steps]


__all__ = ["canonical_json_bytes", "expand", "steps_to_wire"]
