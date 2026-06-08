"""Unit tests for the shared constrained-subset checker.

`cora.shared.json_schema_subset` was hoisted at the
rule-of-three trigger once the third use site landed (Family schema
declaration + Asset settings
union compile + Method parameters declaration). The two BC-specific
wrappers (`equipment.aggregates.capability.settings_validation` and
`recipe.aggregates.method.parameters_validation`) carry their own
deeper test suites for full $schema + jsonschema-rs coverage; this
file is the structural-subset contract pinned ONCE.
"""

from typing import Any

import pytest

from cora.shared.json_schema_subset import (
    ALLOWED_SCHEMA_KEYS,
    DRAFT_2020_12_URI,
    check_schema_is_subset,
    check_subset,
)


class _SubsetError(ValueError):
    """Throwaway error class the test injects into check_subset."""


@pytest.mark.unit
def test_draft_uri_constant_pinned() -> None:
    """The Draft 2020-12 URI is the locked contract; both 5g-a and
    6g-a require schemas to declare exactly this string."""
    assert DRAFT_2020_12_URI == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.unit
def test_allowed_keys_pinned() -> None:
    """Anti-feature pin: widening this set is a deliberate decision
    (and every recursive-keyword addition needs a check_subset
    extension; see the module docstring). `unit` is a non-recursive
    annotation keyword whose value-shape is enforced separately by
    `json_schema_validation.validate_unit_annotations`."""
    assert (
        frozenset(
            {
                "$schema",
                "type",
                "required",
                "properties",
                "enum",
                "minimum",
                "maximum",
                "pattern",
                "unit",
            }
        )
        == ALLOWED_SCHEMA_KEYS
    )


@pytest.mark.unit
def test_check_subset_accepts_unit_annotation_opaque() -> None:
    """`unit` is in the allowlist; the subset checker treats its
    value as opaque and does NOT recurse into it. Shape validation
    of the annotation lives in
    `json_schema_validation.validate_unit_annotations`. This test
    pins the no-recurse contract: a `unit` value that looks
    schema-shaped but contains forbidden keywords must NOT raise here
    (the checker would only catch it if it recursed wrongly)."""
    schema = {
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "unit": {"oneOf": [{"type": "string"}]},
            }
        },
    }
    check_subset(schema, path="<root>", error_class=_SubsetError)


@pytest.mark.unit
def test_check_subset_passes_for_minimal_object() -> None:
    check_subset({"type": "object"}, path="<root>", error_class=_SubsetError)


@pytest.mark.unit
@pytest.mark.parametrize(
    "forbidden_key",
    ["$ref", "oneOf", "anyOf", "allOf", "not", "if", "additionalProperties"],
)
def test_check_subset_raises_caller_error_class_for_forbidden_keyword(
    forbidden_key: str,
) -> None:
    """Caller's error class is what's surfaced — not a generic
    ValueError from the shared helper."""
    schema: dict[str, Any] = {"type": "object", forbidden_key: True}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "forbidden keyword" in str(exc_info.value)
    assert forbidden_key in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_recurses_into_properties() -> None:
    """Forbidden keywords nested inside properties values must also
    raise — the recursion is the pin that prevents shallow holes."""
    schema = {"type": "object", "properties": {"x": {"oneOf": [{"type": "number"}]}}}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "properties.x" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_rejects_non_dict_properties() -> None:
    schema = {"type": "object", "properties": ["a", "b"]}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "must be a dict" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_rejects_non_dict_property_value() -> None:
    schema = {"type": "object", "properties": {"x": "not-a-schema"}}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "must be a schema dict" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_path_is_threaded_through_recursion() -> None:
    """Caller-friendly diagnostics: the path string in the error
    message reflects the recursion depth."""
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"inner": {"oneOf": [{"type": "number"}]}},
            }
        },
    }
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "properties.outer.properties.inner" in str(exc_info.value)


# ---------------------------------------------------------------------------
# check_schema_is_subset
#
# The Recipe BC's `update_method_parameters_schema` decider has its own
# integration-style tests in `tests/unit/recipe/test_update_method_
# parameters_schema_subset.py` that cover the most-load-bearing rules
# (type, properties, required, enum, maximum) through the wrapped error
# class. These tests pin the rules + edge cases that the decider tier
# doesn't already exercise:
#   - minimum narrowing (rule 5)
#   - pattern exact match (rule 7)
#   - unit exact match (rule 8)
#   - graceful skip when sub-shapes are malformed (lines 161, 176, 186)
#   - `_hashable` coercion for list and dict enum values (lines 268-271)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_subset_relation_passes_for_identical_schemas() -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "number", "minimum": 0, "maximum": 10}},
    }
    check_schema_is_subset(schema, schema, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_rejects_widened_minimum() -> None:
    """Method narrowing OK; widening (inner_min < outer_min) rejected."""
    outer = {"type": "object", "properties": {"x": {"type": "number", "minimum": 5}}}
    inner = {"type": "object", "properties": {"x": {"type": "number", "minimum": 1}}}
    with pytest.raises(_SubsetError) as exc_info:
        check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)
    assert "minimum mismatch" in str(exc_info.value)
    assert "$.properties.x" in str(exc_info.value)


@pytest.mark.unit
def test_subset_relation_rejects_pattern_mismatch() -> None:
    """Pattern subsumption is undecidable; subset checker requires exact equality."""
    outer = {"type": "object", "properties": {"sn": {"type": "string", "pattern": "^FLIR-[0-9]+$"}}}
    inner = {"type": "object", "properties": {"sn": {"type": "string", "pattern": "^FLIR-.*$"}}}
    with pytest.raises(_SubsetError) as exc_info:
        check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)
    assert "pattern mismatch" in str(exc_info.value)


@pytest.mark.unit
def test_subset_relation_accepts_equal_patterns() -> None:
    """Pin the equality branch — equal patterns must NOT trigger the rejection."""
    schema = {
        "type": "object",
        "properties": {"sn": {"type": "string", "pattern": "^FLIR-[0-9]+$"}},
    }
    check_schema_is_subset(schema, schema, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_rejects_unit_mismatch() -> None:
    """Units are a `{system, code, label?}` annotation per [[project_units_design]];
    any divergence is rejected because canonical storage assumes one unit per field."""
    outer = {
        "type": "object",
        "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
    }
    inner = {
        "type": "object",
        "properties": {"energy": {"type": "number", "unit": {"system": "udunits", "code": "eV"}}},
    }
    with pytest.raises(_SubsetError) as exc_info:
        check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)
    assert "unit mismatch" in str(exc_info.value)


@pytest.mark.unit
def test_subset_relation_accepts_list_enum_values() -> None:
    """Enum values can themselves be lists (composite enum members);
    `_hashable` coerces them to tuples for set comparison."""
    schema = {
        "type": "object",
        "properties": {"pair": {"enum": [[1, 2], [3, 4]]}},
    }
    check_schema_is_subset(schema, schema, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_accepts_dict_enum_values() -> None:
    """Same `_hashable` coercion for dict enum members."""
    schema = {
        "type": "object",
        "properties": {"preset": {"enum": [{"mode": "fast", "n": 1}, {"mode": "slow", "n": 5}]}},
    }
    check_schema_is_subset(schema, schema, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_skips_when_properties_is_malformed() -> None:
    """Malformed sub-shapes are out of scope here — `check_subset` is the
    structural checker that catches them per-schema. The relation checker
    must skip cleanly so the caller surfaces one well-targeted error
    (from check_subset) instead of two (structural + relation)."""
    outer = {"type": "object", "properties": {"x": {"type": "number"}}}
    inner = {"type": "object", "properties": ["not", "a", "dict"]}
    check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_skips_recurse_when_property_value_is_not_a_dict() -> None:
    """If a property's value is malformed on either side, skip the recurse
    rather than crash. Same rationale as the parent-properties guard."""
    outer = {"type": "object", "properties": {"x": "not-a-schema"}}
    inner = {"type": "object", "properties": {"x": {"type": "number"}}}
    check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)


@pytest.mark.unit
def test_subset_relation_skips_required_check_when_required_is_not_a_list() -> None:
    """`required` is supposed to be a list per JSON Schema, but a malformed
    schema with a non-list `required` must not crash the relation checker."""
    outer = {"type": "object", "properties": {"x": {"type": "number"}}}
    inner = {
        "type": "object",
        "properties": {"x": {"type": "number"}},
        "required": "x",  # malformed: should be a list
    }
    check_schema_is_subset(inner, outer, path="$", error_class=_SubsetError)
