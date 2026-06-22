"""Shared HTTP/MCP wire shapes for the conduct verb-family slices.

`conduct_procedure` and `try_conduct_procedure` accept the SAME step-list
body and surface the SAME per-step failure shape; this BC-level module owns
those wire types + converters so both slices reuse them. A slice cannot
import a sibling slice (the cross-slice-independence fitness), so the shared
seam lives here, outside `features/`, exactly like the resolved-steps replay
helper (`_recipe_expansion/_resolved_steps_replay`) and preparation pipeline
(`_conduct_preparation`).

The Conductor's `Step = SetpointStep | ActionStep | CheckStep` and
`CheckCriterion = EqualsCriterion | WithinToleranceCriterion` discriminated
unions land on the wire as JSON discriminated unions with a `kind` field.
Pydantic's `Field(discriminator="kind")` validates the union at parse time so
a malformed step kind fails the request with a 422 before the handler runs.

Per-step `value` and `criterion.expected` are typed broadly
(`int | float | bool | str | list[Any]`) to match the ControlPort's value
vocabulary. Tuples-on-the-wire arrive as lists; the converter widens to
tuple for the in-process Conductor.
"""

from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, Field

from cora.operation.conductor import (
    ActionStep,
    CheckCriterion,
    CheckStep,
    ConductorFailure,
    EqualsCriterion,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
)

STEP_BATCH_MAX = 500
"""Mirror of `append_activities`'s batch cap. A single conduct request never
carries more than this many steps; larger procedures split client-side via
multiple sequential runs."""


class _SetpointStepRequest(BaseModel):
    """JSON wire shape for a `SetpointStep`."""

    kind: Literal["setpoint"]
    address: str = Field(..., min_length=1)
    value: int | float | bool | str | list[Any]
    verify: bool = False

    model_config = {"extra": "forbid"}


class _ActionStepRequest(BaseModel):
    """JSON wire shape for an `ActionStep`."""

    kind: Literal["action"]
    name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class _EqualsCriterion(BaseModel):
    """JSON wire shape for an `EqualsCriterion`."""

    kind: Literal["equals"]
    expected: int | float | bool | str | list[Any]

    model_config = {"extra": "forbid"}


class _WithinToleranceCriterion(BaseModel):
    """JSON wire shape for a `WithinToleranceCriterion`."""

    kind: Literal["within_tolerance"]
    expected: float
    tolerance: float = Field(..., ge=0.0)

    model_config = {"extra": "forbid"}


_CriterionRequest = Annotated[
    _EqualsCriterion | _WithinToleranceCriterion,
    Field(discriminator="kind"),
]


class _CheckStepRequest(BaseModel):
    """JSON wire shape for a `CheckStep`."""

    kind: Literal["check"]
    address: str = Field(..., min_length=1)
    criterion: _CriterionRequest

    model_config = {"extra": "forbid"}


StepRequest = Annotated[
    _SetpointStepRequest | _ActionStepRequest | _CheckStepRequest,
    Field(discriminator="kind"),
]
"""The wire-side step union a conduct request body carries (`list[StepRequest]`)."""


class ConductorFailureResponse(BaseModel):
    """JSON wire shape for a `ConductorFailure`."""

    step_index: int | None
    source_kind: str
    target: str
    error_class: str
    message: str


def criterion_from_wire(
    wire: _EqualsCriterion | _WithinToleranceCriterion,
) -> CheckCriterion:
    """Build a Conductor `CheckCriterion` from a Pydantic wire model.

    The seam between the JSON shape and the in-process Conductor type; REST
    routes + MCP tools across the conduct family share it.
    """
    if isinstance(wire, _EqualsCriterion):
        expected: Any = wire.expected
        if isinstance(expected, list):
            # wire.expected is a JSON list of Any; tuple-coerce for the in-process EqualsCriterion
            return EqualsCriterion(expected=cast("tuple[Any, ...]", tuple(expected)))  # pyright: ignore[reportUnknownArgumentType]
        return EqualsCriterion(expected=expected)
    return WithinToleranceCriterion(expected=wire.expected, tolerance=wire.tolerance)


def step_from_wire(
    wire: _SetpointStepRequest | _ActionStepRequest | _CheckStepRequest,
) -> Step:
    """Build a Conductor `Step` from a Pydantic wire model (REST + MCP share it)."""
    if isinstance(wire, _SetpointStepRequest):
        value: Any = wire.value
        if isinstance(value, list):
            return SetpointStep(
                address=wire.address,
                value=cast("tuple[Any, ...]", tuple(value)),  # pyright: ignore[reportUnknownArgumentType]
                verify=wire.verify,
            )
        return SetpointStep(address=wire.address, value=value, verify=wire.verify)
    if isinstance(wire, _ActionStepRequest):
        return ActionStep(name=wire.name, params=wire.params)
    return CheckStep(
        address=wire.address,
        criterion=criterion_from_wire(wire.criterion),
    )


def failure_to_wire(failure: ConductorFailure) -> ConductorFailureResponse:
    """Project a `ConductorFailure` onto its JSON wire shape."""
    return ConductorFailureResponse(
        step_index=failure.step_index,
        source_kind=failure.source_kind,
        target=failure.target,
        error_class=failure.error_class,
        message=failure.message,
    )
