"""Structural invariants that lock the Run vs Procedure boundary rule.

See docs/reference/modeling.md#run-vs-procedure-boundary. The rule selects the
spine aggregate by the act's produced output of record: a Dataset-of-record
makes it a Run; a Calibration value or a bare state change makes it a Procedure.
Two facts in the type system already enforce most of that, and this test pins
them against regression:

  - The calibration source union has no `run_id` arm, so a measured / computed
    calibration can only be sourced from a Procedure (or a Dataset, or an actor),
    never a Run. Any act whose output of record is a calibration is therefore a
    Procedure by construction.
  - A Run requires a `plan_id` (it executes a Plan; batch identity), while its
    `subject_id` is optional (the Subject is metadata, not the discriminator;
    calibration captures are subject-less Runs).
"""

import dataclasses
from typing import get_args, get_type_hints

import pytest

from cora.calibration.aggregates.calibration.state import (
    CalibrationSource,
    MeasuredSource,
)
from cora.run.aggregates.run.state import Run


def _union_arms(alias: object) -> tuple[type, ...]:
    # PEP 695 `type X = ...` aliases carry the union on `__value__`.
    return get_args(getattr(alias, "__value__", alias))


@pytest.mark.architecture
def test_calibration_source_has_no_run_id_arm() -> None:
    """No CalibrationSource arm carries `run_id`; the measured value comes from a Procedure.

    If a future arm (or a new field on an existing arm) introduced `run_id`, a
    calibration could be attributed to a Run, letting a calibration-producing act
    masquerade as a Run and breaking the boundary rule.
    """
    arms = _union_arms(CalibrationSource)
    assert arms, "CalibrationSource resolved to no union arms"
    for arm in arms:
        field_names = {f.name for f in dataclasses.fields(arm)}
        assert "run_id" not in field_names, (
            f"{arm.__name__} carries a `run_id` field. The calibration source "
            f"union must have no run-bound arm: a measured calibration is sourced "
            f"from a Procedure, never a Run "
            f"(docs/reference/modeling.md#run-vs-procedure-boundary)."
        )
    measured_fields = {f.name for f in dataclasses.fields(MeasuredSource)}
    assert "procedure_id" in measured_fields, (
        "MeasuredSource must source a measured calibration from a Procedure via `procedure_id`."
    )


@pytest.mark.architecture
def test_run_requires_plan_id_and_subject_is_optional() -> None:
    """`Run.plan_id` is required; `Run.subject_id` is optional.

    plan_id required encodes 'a Run executes a Plan' (batch identity). subject_id
    optional encodes 'the Subject is metadata, not the selector': calibration
    captures are subject-less Runs. If plan_id became Optional or subject_id
    became required, the boundary rule's structural footing would erode.
    """
    hints = get_type_hints(Run)
    assert "plan_id" in hints, "Run has no plan_id field"
    assert type(None) not in get_args(hints["plan_id"]), (
        "Run.plan_id must be required (a Run executes a Plan); it is now Optional "
        "(docs/reference/modeling.md#run-vs-procedure-boundary)."
    )
    assert "subject_id" in hints, "Run has no subject_id field"
    assert type(None) in get_args(hints["subject_id"]), (
        "Run.subject_id must stay Optional: the Subject is metadata, not the "
        "Run-vs-Procedure discriminator (calibration captures are subject-less)."
    )
