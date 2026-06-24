"""Typed `RecipeStep` union and wire-format helpers for Recipe step bodies.

A `Recipe` carries an ordered tuple of `RecipeStep` instances that
expands to a flat sequence of Conductor `Step`s when an operator
binds parameter values via the `register_procedure_from_recipe`
slice (Operation BC). This module ships the type vocabulary and the
wire-format round-trip; the `expand` function that consumes these
VOs into Operation BC `Step`s lives in `cora.operation._recipe_expansion`
because the dependency direction is Operation -> Recipe (Recipe must
not depend on Operation per BC isolation enforced by tach).

## Substitution shape: typed `BindingRef`, not textual `${var}`

Three-pass corpus research established that production beamline and
factory automation systems use typed structures, not textual
interpolation. CORA's codebase convention is frozen dataclasses for
domain models, so `BindingRef(name="dwell")` is a structurally
distinct sentinel from the string `"dwell"`: a literal address
`"2bma:rot:val"` is just a `str`; a binding reference is a
`BindingRef`. The expansion function dispatches on
`isinstance(value, BindingRef)`.

## v1 scope: values bind, addresses do not

Each deployment's Recipe HARDCODES its PV addresses and only
parameterizes operator-tunable VALUES (dwell, repetitions,
angle_start, etc.). At v1 the parameterized positions are:

  - `RecipeSetpointStep.value`
  - `RecipeActionStep.params` (per-key values)
  - `RecipeCheckStep.criterion` thresholds stay literal at v1
    (operators do not tune pass/fail; the criterion is part of the
    Recipe contract)

Addresses + action-body `name` + check-step criterion shapes stay
LITERAL. A v2 trigger to widen address-binding fires when a
deployment ships two near-identical Recipes that differ only in PV
prefix.

## Criterion carrier shape

`RecipeCheckStep.criterion` is a dict-shaped wire payload (the same
`{kind: ..., expected: ...}` shape the Conductor uses for its
CheckStep criterion serialization). The translation to the typed
`EqualsCriterion | WithinToleranceCriterion` union happens in
`cora.operation._recipe_expansion.expand`. This keeps Recipe BC free
of any Operation BC import.

## No `RecipeBody` wrapper VO

Non-emptiness on the step sequence is enforced inside
`Recipe.__post_init__`, not by a wrapper carrier. `to_dict` and
`from_dict` operate on `tuple[RecipeStep, ...]` directly.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class BindingRef:
    """Sentinel value: substitute with `bindings[name]` at expansion time.

    `name` must match a property name in the referenced
    `Capability.parameters_schema`. Binding-reference validation lives
    in the define-recipe-time decider (and re-runs at version_recipe
    and expansion time per [[project-recipe-aggregate-design]] Locks);
    this VO carries the reference shape only.
    """

    name: str


@dataclass(frozen=True)
class CaptureRef:
    """Sentinel value: substitute with the value captured into `capture_name`.

    The runtime sibling of `BindingRef`. Where `BindingRef` resolves at
    EXPANSION time against the frozen operator `bindings` (a pure lookup
    inside the determinism-gated `expand`), a `CaptureRef` resolves at
    EXECUTE time against the Conductor's per-conduct `captures` dict,
    which a prior `CaptureStep` filled with a live reading. `expand`
    passes it through UNCHANGED (it is not a `BindingRef`, so
    `resolve_value` returns it verbatim), so it rides into the conduct
    `Step` and the determinism hash as an opaque sentinel; only the
    Conductor resolves it. `capture_name` must be declared by a
    `RecipeCaptureStep` earlier in the same Recipe (see
    `validate_capture_refs`).
    """

    capture_name: str


@dataclass(frozen=True)
class RecipeSetpointStep:
    """Setpoint step template: `value` is a literal, a `BindingRef`, or a `CaptureRef`.

    `address` is hardcoded per Recipe (no parameterization at v1 per
    the v1 scope note in the module docstring); `value` is the only
    bindable position. `verify` mirrors `SetpointStep.verify` exactly.
    A `CaptureRef` value rides through expansion unresolved and is
    resolved by the Conductor at execute time against the captured value.
    """

    address: str
    value: int | float | bool | str | tuple[Any, ...] | BindingRef | CaptureRef
    verify: bool = False


@dataclass(frozen=True)
class RecipeActionStep:
    """Action step template: each `params` value may be a literal or `BindingRef`.

    `name` is the registered action-body name; not parameterized.
    `params` values may individually be `BindingRef` sentinels; the
    expansion function walks the mapping and substitutes per-key.
    `CaptureRef` is NOT supported in `params` at v1 (only in
    `RecipeSetpointStep.value`); action-param capture is deferred until a
    consumer needs it.
    """

    name: str
    params: Mapping[str, Any | BindingRef] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class RecipeCheckStep:
    """Check step template: `criterion` is the wire-format dict.

    Carrying the criterion as a `{kind: ..., expected: ..., tolerance?: ...}`
    dict lets Recipe BC define the step VO without importing the typed
    criterion classes from Operation BC. The expansion function in
    `cora.operation._recipe_expansion` translates the dict to the typed
    `EqualsCriterion | WithinToleranceCriterion` union at runtime.

    Recognized kinds today: `"equals"`, `"within_tolerance"`. The
    expansion function raises `ValueError` for unknown kinds.
    """

    address: str
    criterion: Mapping[str, Any]


@dataclass(frozen=True)
class RecipeCaptureStep:
    """Capture step template: read `address` at execute time into `capture_name`.

    The recipe-template twin of the Conductor's `CaptureStep`. It carries
    no bindable value (the read is the value); `address` is hardcoded per
    Recipe like the other steps. A later step references the captured
    value via `CaptureRef(capture_name)`.
    """

    address: str
    capture_name: str


@dataclass(frozen=True)
class RecipeComputeStep:
    """Compute step template: submit `command` over ComputePort, surface a Measurement.

    The recipe-template twin of the Conductor's `ComputeStep` (slice 6a).
    Fields are LITERAL at 6a (no `BindingRef` on a compute step yet): the
    `command` argv + `input_uris` (authored literal URIs pointing at the
    well-known paths the acquisition action bodies wrote) + optional
    `output_uri` + literal `parameters`. The expansion function passes the
    fields through verbatim; binding a compute parameter is a deferred
    widening (the first deployment that needs an operator-tunable compute
    parameter fires it).
    """

    command: tuple[str, ...]
    input_uris: tuple[str, ...] = ()
    output_uri: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict[str, Any])


RecipeStep = (
    RecipeSetpointStep | RecipeActionStep | RecipeCheckStep | RecipeCaptureStep | RecipeComputeStep
)
"""Closed discriminated union of templated step shapes; parallels `Step` arm-for-arm."""


class UnboundRecipeBindingError(Exception):
    """A `BindingRef.name` did not resolve in the supplied `bindings` mapping.

    Family: `Invalid<X>`. The central REST handler maps this to HTTP 422.
    Renamed from the worktree's `UnboundBindingError` as part of the
    Recipe rename pass.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"unbound binding reference: {name!r}")
        self.name = name


class InvalidRecipeStepShapeError(Exception):
    """Wire-format dict could not be parsed into a `RecipeStep`.

    Raised by `from_dict` for unknown step kinds, missing required
    keys, or structurally malformed payloads. Family: `Invalid<X>`.
    HTTP 422 (parse failure after Pydantic boundary).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"recipe step wire shape invalid: {reason}")
        self.reason = reason


_BINDING_KEY = "__binding__"
"""Wire-format key distinguishing a `BindingRef` from a literal dict value.

A literal `dict` value in `params` MUST NOT carry this key at v1; the
wire format does not currently support escaping. If a future deployment
needs to bind a dict-typed parameter that happens to carry this exact
key, widen the escape rule then (no current consumer)."""

_CAPTURE_KEY = "__capture__"
"""Wire-format key distinguishing a `CaptureRef` from a literal dict value.

Same escape caveat as `_BINDING_KEY`: a literal `dict` value MUST NOT
carry this key at v1."""


def _value_to_wire(value: Any | BindingRef | CaptureRef) -> Any:
    """Serialize one value (literal, BindingRef, or CaptureRef) to JSON-friendly form."""
    if isinstance(value, BindingRef):
        return {_BINDING_KEY: value.name}
    if isinstance(value, CaptureRef):
        return {_CAPTURE_KEY: value.capture_name}
    return value


def _value_from_wire(value: Any) -> Any:
    """Deserialize one wire value; reconstruct a BindingRef / CaptureRef sentinel.

    Returns the original value (literal) or the reconstructed sentinel VO.
    Signature widens to `Any` because callers store the result into
    mappings whose value-type is also `Any`; a narrower union does not
    help downstream type-checking.
    """
    if isinstance(value, dict):
        typed = cast("dict[str, Any]", value)
        if set(typed.keys()) == {_BINDING_KEY}:
            return BindingRef(name=typed[_BINDING_KEY])
        if set(typed.keys()) == {_CAPTURE_KEY}:
            return CaptureRef(capture_name=typed[_CAPTURE_KEY])
    return cast("Any", value)


def _step_to_wire(step: RecipeStep) -> dict[str, Any]:
    if isinstance(step, RecipeSetpointStep):
        return {
            "kind": "setpoint",
            "address": step.address,
            "value": _value_to_wire(step.value),
            "verify": step.verify,
        }
    if isinstance(step, RecipeActionStep):
        return {
            "kind": "action",
            "name": step.name,
            "params": {key: _value_to_wire(val) for key, val in step.params.items()},
        }
    if isinstance(step, RecipeCaptureStep):
        return {
            "kind": "capture",
            "address": step.address,
            "capture_name": step.capture_name,
        }
    if isinstance(step, RecipeComputeStep):
        return {
            "kind": "compute",
            "command": list(step.command),
            "input_uris": list(step.input_uris),
            "output_uri": step.output_uri,
            "parameters": dict(step.parameters),
        }
    return {
        "kind": "check",
        "address": step.address,
        "criterion": dict(step.criterion),
    }


def _step_from_wire(payload: dict[str, Any]) -> RecipeStep:
    try:
        kind = payload["kind"]
    except (KeyError, TypeError) as exc:
        raise InvalidRecipeStepShapeError("step missing 'kind'") from exc
    try:
        if kind == "setpoint":
            return RecipeSetpointStep(
                address=payload["address"],
                value=_value_from_wire(payload["value"]),
                verify=payload.get("verify", False),
            )
        if kind == "action":
            return RecipeActionStep(
                name=payload["name"],
                params={key: _value_from_wire(val) for key, val in payload["params"].items()},
            )
        if kind == "capture":
            return RecipeCaptureStep(
                address=payload["address"],
                capture_name=payload["capture_name"],
            )
        if kind == "compute":
            return RecipeComputeStep(
                command=tuple(payload["command"]),
                input_uris=tuple(payload.get("input_uris", ())),
                output_uri=payload.get("output_uri"),
                parameters=dict(payload.get("parameters", {})),
            )
        if kind == "check":
            return RecipeCheckStep(
                address=payload["address"],
                criterion=dict(payload["criterion"]),
            )
    except (KeyError, AttributeError, TypeError) as exc:
        raise InvalidRecipeStepShapeError(f"step kind {kind!r}: {exc}") from exc
    raise InvalidRecipeStepShapeError(f"unknown recipe step kind: {kind!r}")


def to_dict(steps: tuple[RecipeStep, ...]) -> dict[str, Any]:
    """Serialize a Recipe step sequence to a JSON-friendly dict for event storage.

    Returns a wrapper dict with a single `steps` list, mirroring the
    worktree wire format. Callers store the result directly in a
    `RecipeDefined` or `RecipeVersioned` payload.
    """
    return {"steps": [_step_to_wire(step) for step in steps]}


def from_dict(payload: dict[str, Any]) -> tuple[RecipeStep, ...]:
    """Rebuild a Recipe step sequence from its wire-format dict.

    Returns `tuple[RecipeStep, ...]` directly; does NOT enforce
    non-emptiness (that invariant is carried by `Recipe.__post_init__`
    when the steps are folded into a `Recipe(...)` instance).

    Raises `InvalidRecipeStepShapeError` for unknown step kinds or
    structurally malformed payloads.
    """
    try:
        raw_steps = payload["steps"]
    except (KeyError, TypeError) as exc:
        raise InvalidRecipeStepShapeError("payload missing 'steps'") from exc
    return tuple(_step_from_wire(s) for s in raw_steps)


def resolve_value(value: Any | BindingRef, bindings: Mapping[str, Any]) -> Any:
    """Resolve a single value (literal or BindingRef) against `bindings`.

    Public helper the Operation BC `expand` function uses to substitute
    one value at a time without duplicating the BindingRef-aware lookup
    logic. Raises `UnboundRecipeBindingError` when a BindingRef name is
    missing from `bindings`.
    """
    if isinstance(value, BindingRef):
        if value.name not in bindings:
            raise UnboundRecipeBindingError(value.name)
        return bindings[value.name]
    return value


class UnboundRecipeCaptureError(Exception):
    """A `CaptureRef.capture_name` is not declared by a preceding `RecipeCaptureStep`.

    Family: `Invalid<X>`. HTTP 422. A `CaptureRef` must reference a value
    captured EARLIER in the same Recipe; a forward or missing reference is
    an authoring error caught at define-recipe time.
    """

    def __init__(self, capture_name: str) -> None:
        super().__init__(
            f"capture reference {capture_name!r} not declared by a preceding capture step"
        )
        self.capture_name = capture_name


class DuplicateRecipeCaptureError(Exception):
    """A `RecipeCaptureStep` re-declares a `capture_name` already captured.

    Family: `Invalid<X>`. HTTP 422. Re-capturing into an already-filled
    name within one Recipe is rejected as an authoring error (the lock):
    a second capture of the same name is almost certainly a mistake.
    """

    def __init__(self, capture_name: str) -> None:
        super().__init__(f"capture name {capture_name!r} declared more than once")
        self.capture_name = capture_name


def _check_capture_ref(value: Any, declared: set[str]) -> None:
    if isinstance(value, CaptureRef) and value.capture_name not in declared:
        raise UnboundRecipeCaptureError(value.capture_name)


def validate_capture_refs(steps: tuple[RecipeStep, ...]) -> None:
    """Every `CaptureRef` must reference a `capture_name` declared earlier.

    Pure structural check (no I/O), run at define-recipe time. Walks the
    steps in order: a `RecipeCaptureStep` declares its `capture_name`
    (duplicate declaration -> `DuplicateRecipeCaptureError`); a `CaptureRef`
    in a later setpoint value or action param must reference an
    already-declared name (forward / missing -> `UnboundRecipeCaptureError`).
    """
    declared: set[str] = set()
    for step in steps:
        if isinstance(step, RecipeCaptureStep):
            if step.capture_name in declared:
                raise DuplicateRecipeCaptureError(step.capture_name)
            declared.add(step.capture_name)
        elif isinstance(step, RecipeSetpointStep):
            _check_capture_ref(step.value, declared)


__all__ = [
    "BindingRef",
    "CaptureRef",
    "DuplicateRecipeCaptureError",
    "InvalidRecipeStepShapeError",
    "RecipeActionStep",
    "RecipeCaptureStep",
    "RecipeCheckStep",
    "RecipeComputeStep",
    "RecipeSetpointStep",
    "RecipeStep",
    "UnboundRecipeBindingError",
    "UnboundRecipeCaptureError",
    "from_dict",
    "resolve_value",
    "to_dict",
    "validate_capture_refs",
]
