"""Validate Run effective_parameters against the owning Method's
parameters_schema and validate adjusted parameters
against the schema for steering slices.

The 6g-a Method-side checker validates the SHAPE of the schema
itself. The 6g-b Plan-side validator validates DEFAULTS. This
module is the Run-side equivalent for the carrier aggregate: two
sibling adapters cover the two postures the Run BC needs.

  - `validate_effective_parameters_against_method_schema` — STRICT
    posture used by `start_run` (6g-c). Schemaless Method + non-empty
    parameters REJECTS. Forces operators to declare a schema before
    accepting overrides at Run start time. Mirrors 5g-c's
    "no Capabilities + non-empty settings → reject" anchor.
  - `validate_adjusted_parameters_against_method_schema` — RELAXED
    posture used by `adjust_run` (6j) and future steering slices.
    Schemaless Method + non-empty parameters SKIPS validation. Once
    an operator has started a Run on a schemaless Method, they carry
    full responsibility for steering it; we don't second-guess at
    adjust time.

Both delegate to the shared values-validator at
`cora.shared.json_schema_validation` and surface
Run-specific error classes for unambiguous API responses.

## Module shape

Thin BC-specific adapters: error classes live on
`run.aggregates.run.state` (next to other Run domain errors), each
adapter is a one-liner that delegates to the shared validator. The
two postures coexist intentionally and are NOT to be unified. See
[[project_adjust_run_design]] §Locks (merged-result-must-satisfy-
schema, 5g-c STRICT anchor) for the RELAXED-at-adjust rationale and
[[project_schema_validated_values_pattern]] for the cross-BC
implementation pattern. See `docs/reference/patterns.md` "Schema
validation posture" for the operator-vocabulary mapping.
"""

from collections.abc import Mapping
from typing import Any

from cora.run.aggregates.run.state import (
    InvalidRunAdjustSchemaError,
    InvalidRunParametersError,
)
from cora.shared.json_schema_validation import validate_values_against_schema

_NO_SCHEMA_MESSAGE = (
    "Method declares no parameters_schema; cannot start Run with "
    "resolved parameters {keys}. Either declare a parameters_schema "
    "on the Method (an empty `{{}}` is valid for parameter-less "
    "Methods) or omit override_parameters AND clear Plan defaults."
)


def validate_effective_parameters_against_method_schema(
    effective_parameters: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `effective_parameters` against the Method's schema
    (STRICT posture; used by `start_run`, 6g-c).

    Strict when `method_parameters_schema is None`: empty effective
    parameters pass trivially, but ANY non-empty effective dict
    raises `InvalidRunParametersError` with operator guidance.
    Delegates to the shared values-validator.

    Sibling: `validate_adjusted_parameters_against_method_schema`
    (RELAXED posture; used by `adjust_run`, 6j). The two postures
    are intentional and coexist; see module docstring.
    """
    validate_values_against_schema(
        effective_parameters,
        method_parameters_schema,
        error_class=InvalidRunParametersError,
        no_schema_message=_NO_SCHEMA_MESSAGE,
    )


def validate_adjusted_parameters_against_method_schema(
    merged_parameters: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate adjusted (post-merge) parameters against the Method's
    schema (RELAXED posture; used by `adjust_run`, 6j and future
    steering slices).

    Unlike the STRICT
    `validate_effective_parameters_against_method_schema` (used by
    `start_run`; rejects schemaless Method + non-empty parameters),
    this adapter SKIPS validation entirely when
    `method_parameters_schema is None`. Schemaless Methods are
    operator-trusted at adjust time per the
    [[project_adjust_run_design]] memo §Locks
    "merged-result-must-satisfy-schema (5g-c STRICT anchor)"
    rationale: once an operator has started a Run with a schemaless
    Method, they have full responsibility for steering it; we don't
    second-guess at adjust time.

    The two postures coexist intentionally and are NOT to be unified.
    See `docs/reference/patterns.md` "Schema validation posture" for
    the cross-BC convention.
    """
    validate_values_against_schema(
        merged_parameters,
        method_parameters_schema,
        error_class=InvalidRunAdjustSchemaError,
        # no_schema_message=None → RELAXED dispatch: schemaless skips.
    )


__all__ = [
    "validate_adjusted_parameters_against_method_schema",
    "validate_effective_parameters_against_method_schema",
]
