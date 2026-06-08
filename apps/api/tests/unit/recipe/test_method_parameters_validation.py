"""Unit tests for the Method parameters_schema validator.

Pins the constrained JSON Schema subset CORA accepts for
Method.parameters_schema. Same subset as Family.settings_schema
(5g-a); the two share the underlying checker via
`cora.shared.json_schema_subset`. Symmetry is the point —
this file mirrors `tests/unit/equipment/test_capability_settings_validation.py`
case for case, so the two BC-specific wrappers stay aligned.
"""

from typing import Any

import pytest

from cora.recipe.aggregates.method.parameters_validation import (
    InvalidMethodParametersSchemaError,
    validate_parameters_schema,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(**body: Any) -> dict[str, Any]:
    """Helper: build a schema dict with the required $schema declaration."""
    return {"$schema": _DRAFT, **body}


@pytest.mark.unit
def test_accepts_minimal_object_schema() -> None:
    validate_parameters_schema(_schema(type="object"))


@pytest.mark.unit
def test_accepts_full_subset() -> None:
    """Every keyword in the allowed subset should pass."""
    validate_parameters_schema(
        _schema(
            type="object",
            required=["energy"],
            properties={
                "energy": {
                    "type": "number",
                    "minimum": 5,
                    "maximum": 50,
                    "unit": {"system": "udunits", "code": "keV"},
                },
                "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo"]},
                "exposure": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5000,
                    "unit": {"system": "udunits", "code": "ms"},
                },
                "detector_serial": {"type": "string", "pattern": "^FLIR-[0-9]+$"},
            },
        )
    )


@pytest.mark.unit
def test_rejects_missing_dollar_schema() -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema({"type": "object"})
    assert "$schema must be exactly" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_wrong_dollar_schema_uri() -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(
            {
                "$schema": "https://json-schema.org/draft-07/schema#",
                "type": "object",
            }
        )
    assert "$schema must be exactly" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "forbidden_key",
    ["$ref", "oneOf", "anyOf", "allOf", "not", "if", "additionalProperties"],
)
def test_rejects_forbidden_top_level_keyword(forbidden_key: str) -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(_schema(**{forbidden_key: True}))
    assert "forbidden keyword" in exc_info.value.reason
    assert forbidden_key in exc_info.value.reason


@pytest.mark.unit
def test_rejects_forbidden_keyword_nested_in_properties() -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(_schema(type="object", properties={"x": {"$ref": "#/defs/foo"}}))
    assert "$ref" in exc_info.value.reason
    assert "properties.x" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_properties_value_that_is_not_a_dict() -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(_schema(type="object", properties={"x": "not-a-schema"}))
    assert "must be a schema dict" in exc_info.value.reason


@pytest.mark.unit
def test_rejects_properties_that_is_not_a_dict() -> None:
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(_schema(type="object", properties=["a", "b"]))
    assert "must be a dict" in exc_info.value.reason


@pytest.mark.unit
def test_accepts_empty_properties_dict() -> None:
    validate_parameters_schema(_schema(type="object", properties={}))


@pytest.mark.unit
def test_accepts_nested_properties_with_subset_only() -> None:
    validate_parameters_schema(
        _schema(
            type="object",
            properties={
                "trajectory": {
                    "type": "object",
                    "properties": {
                        "start_position": {
                            "type": "number",
                            "unit": {"system": "udunits", "code": "mm"},
                        },
                        "stop_position": {
                            "type": "number",
                            "unit": {"system": "udunits", "code": "mm"},
                        },
                    },
                    "required": ["start_position"],
                },
            },
        )
    )


@pytest.mark.unit
def test_accepts_nested_dollar_schema_declaration() -> None:
    """Nested property-schemas may carry their own `$schema` even
    though only the root NEEDS one. Same posture as 5g-a."""
    validate_parameters_schema(
        _schema(
            type="object",
            properties={
                "trajectory": {
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {
                        "start_position": {
                            "type": "number",
                            "unit": {"system": "udunits", "code": "mm"},
                        }
                    },
                },
            },
        )
    )


@pytest.mark.unit
def test_rejects_malformed_schema_via_jsonschema_rs() -> None:
    """If the schema is in-subset but jsonschema-rs rejects it as
    malformed (for example, an invalid `pattern` regex), we surface
    that as InvalidMethodParametersSchemaError."""
    with pytest.raises(InvalidMethodParametersSchemaError) as exc_info:
        validate_parameters_schema(
            _schema(
                type="object",
                properties={"x": {"type": "string", "pattern": "[invalid(regex"}},
            )
        )
    assert "Invalid Method parameters_schema" in str(exc_info.value)
