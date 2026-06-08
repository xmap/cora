"""Validate Method.parameters_schema against CORA's constrained
JSON Schema subset.

Method.parameters_schema declares the shape of parameter dicts that
downstream Plans and Runs carry for this Method. This
module is the write-time guard via the shared declarer-validator at
`cora.shared.json_schema_validation`. The runtime values
validation uses the values-against-schema function in the
same shared module via Plan / Run thin wrappers.

## Module shape

This module is a thin BC-specific adapter: it defines the
`InvalidMethodParametersSchemaError` exception class and a
one-liner `validate_parameters_schema` that delegates to the
shared validator. Mirrors the Family schema-validation
adapter shape.
"""

from typing import Any

from cora.shared.json_schema_validation import validate_schema_declaration


class InvalidMethodParametersSchemaError(ValueError):
    """The supplied Method parameters_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Three failure modes (handled by the shared validator):
      1. Schema is not well-formed JSON Schema (jsonschema-rs raises
         on `Validator(schema)` construction).
      2. Schema uses a forbidden keyword (`$ref`, `oneOf`, etc.).
      3. Schema is missing the required `$schema` declaration.

    Mapped to HTTP 400 by the recipe BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Method parameters_schema: {reason}")
        self.reason = reason


def validate_parameters_schema(schema: dict[str, Any]) -> None:
    """Validate that `schema` is a well-formed in-subset JSON Schema.

    Raises `InvalidMethodParametersSchemaError(reason)` on
    missing/wrong `$schema`, forbidden keyword, or jsonschema-rs
    malformedness. Delegates to the shared declarer-validator.
    """
    validate_schema_declaration(schema, error_class=InvalidMethodParametersSchemaError)


__all__ = [
    "InvalidMethodParametersSchemaError",
    "validate_parameters_schema",
]
