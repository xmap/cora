"""Shared HTTP/MCP wire shapes for the steered-conduct (`conduct_until_advised`) slice.

The six-noun Steering model (`cora.operation.ports.decide_port`) is in-process
frozen dataclasses; this BC-level module owns their Pydantic wire mirrors +
converters so the route and the MCP tool share one shape (a slice cannot import
a sibling slice, so the seam lives here, beside `_conduct_wire`).

These are plain VOs (not discriminated unions like the criterion): an objective,
a search space of axes, an optional budget, and the brain-selection config. The
per-step failure shape is reused from `_conduct_wire` (the loop surfaces the
same `ConductorFailure`).
"""

from typing import Any

from pydantic import BaseModel, Field

from cora.operation.adapters.decide_port_config import DecidePortConfig, WireDecideSubstrate
from cora.operation.ports.decide_port import (
    SteeringAxis,
    SteeringBudget,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)


class SteeringObjectiveRequest(BaseModel):
    """JSON wire shape for a `SteeringObjective`."""

    kind: SteeringObjectiveKind = Field(
        ...,
        description=(
            "What good means: Minimize / Maximize / Satisfy / Explore. The brain "
            "weighs it; a grid walker only early-stops on a met Satisfy target."
        ),
    )
    target_measurement_name: str | None = Field(
        default=None,
        description="Name of the objective measurement the brain reads (None for pure Explore).",
    )
    target_value: float | None = Field(
        default=None,
        description="Setpoint the objective drives toward (used by Satisfy; None otherwise).",
    )

    model_config = {"extra": "forbid"}


class SteeringAxisRequest(BaseModel):
    """JSON wire shape for a `SteeringAxis`."""

    name: str = Field(
        ...,
        min_length=1,
        description=(
            "Axis label the brain proposes coordinates for; must be consumed by a "
            "SteeringRef setpoint in the pinned recipe block."
        ),
    )
    lower: float | None = Field(default=None, description="Lower bound for a continuous axis.")
    upper: float | None = Field(default=None, description="Upper bound for a continuous axis.")
    choices: list[Any] = Field(
        default_factory=list,
        description="Enumerated values for a discrete/categorical axis (empty for continuous).",
    )

    model_config = {"extra": "forbid"}


class SteeringSpaceRequest(BaseModel):
    """JSON wire shape for a `SteeringSpace`."""

    axes: list[SteeringAxisRequest] = Field(
        ...,
        min_length=1,
        description="The feasible set the brain may propose within.",
    )

    model_config = {"extra": "forbid"}


class SteeringBudgetRequest(BaseModel):
    """JSON wire shape for a `SteeringBudget` (informational for the brain)."""

    iterations_remaining: int | None = Field(default=None, ge=0)
    wall_clock_seconds_remaining: float | None = Field(default=None, ge=0.0)

    model_config = {"extra": "forbid"}


class DecideConfigRequest(BaseModel):
    """JSON wire shape selecting the in-CORA brain behind the DecidePort."""

    substrate: WireDecideSubstrate = Field(
        default="grid_walk",
        description="Which in-CORA decider drives the loop: 'in_memory' or 'grid_walk'.",
    )
    points_per_axis: int = Field(
        default=5,
        ge=1,
        description="Grid-walk resolution for continuous axes (ignored by in_memory and choices).",
    )

    model_config = {"extra": "forbid"}


def objective_from_wire(wire: SteeringObjectiveRequest) -> SteeringObjective:
    """Build a `SteeringObjective` from its Pydantic wire model."""
    return SteeringObjective(
        kind=wire.kind,
        target_measurement_name=wire.target_measurement_name,
        target_value=wire.target_value,
    )


def space_from_wire(wire: SteeringSpaceRequest) -> SteeringSpace:
    """Build a `SteeringSpace` from its Pydantic wire model (lists -> tuples)."""
    return SteeringSpace(
        axes=tuple(
            SteeringAxis(
                name=axis.name,
                lower=axis.lower,
                upper=axis.upper,
                choices=tuple(axis.choices),
            )
            for axis in wire.axes
        )
    )


def budget_from_wire(wire: SteeringBudgetRequest | None) -> SteeringBudget | None:
    """Build a `SteeringBudget` from its Pydantic wire model (None passes through)."""
    if wire is None:
        return None
    return SteeringBudget(
        iterations_remaining=wire.iterations_remaining,
        wall_clock_seconds_remaining=wire.wall_clock_seconds_remaining,
    )


def decide_from_wire(wire: DecideConfigRequest) -> DecidePortConfig:
    """Build a `DecidePortConfig` from its Pydantic wire model."""
    return DecidePortConfig(substrate=wire.substrate, points_per_axis=wire.points_per_axis)
