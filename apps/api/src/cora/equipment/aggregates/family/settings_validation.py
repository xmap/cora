"""Validate Family.settings_schema against CORA's constrained
JSON Schema subset.

Family.settings_schema declares the shape of Asset.settings keys
this Family "owns". This module is the write-time guard via the
shared declarer-validator at
`cora.shared.json_schema_validation`.

## Constrained subset

See `cora.shared.json_schema_subset` for the allowed
keyword whitelist (`$schema`, `type`, `required`, `properties`,
`enum`, `minimum`, `maximum`, `pattern`). Forbidden everywhere:
`$ref`, `oneOf`, `anyOf`, `allOf`, `not`, conditionals.
"""

from typing import Any

from cora.shared.json_schema_validation import validate_schema_declaration


class InvalidFamilySettingsSchemaError(ValueError):
    """The supplied Family settings_schema is not a valid JSON
    Schema in CORA's constrained subset.

    Three failure modes (handled by the shared validator):
      1. Schema is not well-formed JSON Schema.
      2. Schema uses a forbidden keyword (`$ref`, `oneOf`, etc.).
      3. Schema is missing the required `$schema` declaration.

    Mapped to HTTP 400 by the equipment BC's exception handler.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Family settings_schema: {reason}")
        self.reason = reason


def validate_settings_schema(schema: dict[str, Any]) -> None:
    """Validate that `schema` is a well-formed in-subset JSON Schema.

    Raises `InvalidFamilySettingsSchemaError(reason)` on missing/wrong
    `$schema`, forbidden keyword, or jsonschema-rs malformedness.
    """
    validate_schema_declaration(schema, error_class=InvalidFamilySettingsSchemaError)


__all__ = [
    "InvalidFamilySettingsSchemaError",
    "validate_settings_schema",
]
