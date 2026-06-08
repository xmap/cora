"""Validate Plan.default_parameters against the owning Method's
parameters_schema.

The Method-side checker validates the SHAPE of the schema
itself. This module validates VALUES against that schema by
delegating to the shared values-validator at
`cora.shared.json_schema_validation`. Strict-by-default
when the schema is None; mirrors Asset.settings's
"no Capabilities + non-empty settings → reject" anchor.

## Module shape

Thin BC-specific adapter: defines `InvalidPlanDefaultParametersError`
on `plan.state` (next to other Plan domain errors) + a one-liner
`validate_default_parameters_against_method_schema` that delegates
to the shared validator with the Plan-specific operator-facing
error message. See [[project_run_parameters_design]] §audit-correction
for the strict posture rationale and
[[project_schema_validated_values_pattern]] for the cross-BC
implementation pattern.
"""

from collections.abc import Mapping
from typing import Any

from cora.recipe.aggregates.plan.state import InvalidPlanDefaultParametersError
from cora.shared.json_schema_validation import validate_values_against_schema

_NO_SCHEMA_MESSAGE = (
    "Method declares no parameters_schema; cannot accept defaults "
    "for key(s) {keys}. Either declare a parameters_schema (an empty "
    "`{{}}` is valid for parameter-less Methods) or omit the defaults."
)


def validate_default_parameters_against_method_schema(
    default_parameters: Mapping[str, Any],
    method_parameters_schema: dict[str, Any] | None,
) -> None:
    """Validate `default_parameters` against the Method's schema.

    Strict when `method_parameters_schema is None`: empty defaults
    pass trivially, but ANY non-empty defaults dict raises
    `InvalidPlanDefaultParametersError` with operator guidance.
    Delegates to the shared values-validator.
    """
    validate_values_against_schema(
        default_parameters,
        method_parameters_schema,
        error_class=InvalidPlanDefaultParametersError,
        no_schema_message=_NO_SCHEMA_MESSAGE,
    )


__all__ = ["validate_default_parameters_against_method_schema"]
