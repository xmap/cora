"""Unit tests for the shared JSON Schema declaration / unit-annotation
validators.

Most of `cora.shared.json_schema_validation` is exercised
indirectly via each BC's wrapper (5g-a Family, 6g-a Method, 6g-b
Plan, 6g-c Run, 5g-c Asset). This file pins the cross-BC pieces ONCE
to keep their contract scannable:

  - `ALLOWED_UNIT_SYSTEMS` namespace allowlist (anti-feature pin)
  - `validate_unit_annotations` shape contract for the `unit`
    custom annotation (per [[project_units_design]])
  - `validate_schema_declaration` calls through to unit-annotation
    checking after `check_subset`, surfacing the caller's error class

Mirrors `test_json_schema_subset.py`'s structural-pin role.
"""

from typing import Any

import pytest

from cora.shared.json_schema_subset import DRAFT_2020_12_URI
from cora.shared.json_schema_validation import (
    ALLOWED_UNIT_SYSTEMS,
    validate_schema_declaration,
    validate_unit_annotations,
)


class _ValidationError(ValueError):
    """Throwaway error class the tests inject (mirrors what each BC's
    wrapper passes in, for example `InvalidMethodParametersSchemaError`)."""


@pytest.mark.unit
def test_allowed_unit_systems_pinned() -> None:
    """Anti-feature pin: widening the namespace allowlist is a
    deliberate decision driven by a real consumer at a seam, per
    [[project_units_design]]."""
    assert frozenset({"udunits", "ucum", "qudt", "iec61360", "ucefact"}) == ALLOWED_UNIT_SYSTEMS


@pytest.mark.unit
def test_validate_unit_annotations_no_op_when_absent() -> None:
    """Schemas without any `unit` annotations are the common case; the
    validator must be a silent no-op so non-numeric schemas pay no
    cost."""
    schema = {
        "type": "object",
        "properties": {
            "detector_serial": {"type": "string"},
            "filter_material": {"type": "string"},
        },
    }
    validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)


@pytest.mark.unit
def test_validate_unit_annotations_accepts_minimal_valid_shape() -> None:
    schema = {
        "type": "object",
        "properties": {
            "energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}},
        },
    }
    validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)


@pytest.mark.unit
def test_validate_unit_annotations_accepts_optional_label() -> None:
    schema = {
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "unit": {
                    "system": "udunits",
                    "code": "keV",
                    "label": "kiloelectronvolts",
                },
            },
        },
    }
    validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)


@pytest.mark.unit
def test_validate_unit_annotations_accepts_qudt_iri_code() -> None:
    """Codes are opaque-within-namespace: a QUDT IRI is valid as the
    `code` value when `system='qudt'`."""
    schema = {
        "type": "object",
        "properties": {
            "position": {
                "type": "number",
                "unit": {
                    "system": "qudt",
                    "code": "http://qudt.org/vocab/unit/MilliM",
                },
            },
        },
    }
    validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)


@pytest.mark.unit
def test_validate_unit_annotations_recurses_into_nested_object_properties() -> None:
    """A nested object property's unit annotation must also be
    validated; mirrors `check_subset`'s recursion shape."""
    schema = {
        "type": "object",
        "properties": {
            "trajectory": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "number",
                        "unit": {"system": "udunits", "code": "mm"},
                    },
                    "speed": {
                        "type": "number",
                        "unit": {"system": "BOGUS", "code": "mm/s"},
                    },
                },
            },
        },
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    msg = str(exc_info.value)
    assert "properties.trajectory.properties.speed.unit" in msg
    assert "BOGUS" in msg


@pytest.mark.unit
def test_validate_unit_annotations_rejects_non_dict_annotation() -> None:
    schema = {
        "type": "object",
        "properties": {"energy": {"type": "number", "unit": "keV"}},
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    assert "must be a dict" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("annotation", "expected_missing"),
    [
        ({"code": "mm"}, "system"),
        ({"system": "udunits"}, "code"),
        ({}, "code"),
    ],
)
def test_validate_unit_annotations_rejects_missing_required_keys(
    annotation: dict[str, Any], expected_missing: str
) -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "number", "unit": annotation}},
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    msg = str(exc_info.value)
    assert "missing required keys" in msg
    assert expected_missing in msg


@pytest.mark.unit
def test_validate_unit_annotations_rejects_unknown_keys() -> None:
    """Tight allowlist: arbitrary extra fields are not tolerated. If a
    future need appears (for example `description`, or per-namespace
    metadata), it gets a deliberate addition to the allowed-keys set
    with the same anti-feature scrutiny as ALLOWED_UNIT_SYSTEMS."""
    schema = {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "unit": {
                    "system": "udunits",
                    "code": "mm",
                    "display_unit": "in",
                },
            }
        },
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    msg = str(exc_info.value)
    assert "unknown keys" in msg
    assert "display_unit" in msg


@pytest.mark.unit
@pytest.mark.parametrize("system", ["UDUNITS", "fhir", "si", "", "udunit"])
def test_validate_unit_annotations_rejects_system_outside_allowlist(
    system: str,
) -> None:
    """The allowlist is closed and case-sensitive. `UDUNITS` is NOT a
    synonym for `udunits`. New systems are added by deliberate edit
    to ALLOWED_UNIT_SYSTEMS, not by accident."""
    schema = {
        "type": "object",
        "properties": {"x": {"type": "number", "unit": {"system": system, "code": "mm"}}},
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    assert "not in CORA's allowed" in str(exc_info.value)


@pytest.mark.unit
def test_validate_unit_annotations_rejects_non_string_system() -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "number", "unit": {"system": 1, "code": "mm"}}},
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    assert "must be a string" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize("code", ["", 0, None, 1.5])
def test_validate_unit_annotations_rejects_empty_or_non_string_code(
    code: Any,
) -> None:
    schema = {
        "type": "object",
        "properties": {"x": {"type": "number", "unit": {"system": "udunits", "code": code}}},
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    assert "must be a non-empty string" in str(exc_info.value)


@pytest.mark.unit
def test_validate_unit_annotations_rejects_non_string_label() -> None:
    schema = {
        "type": "object",
        "properties": {
            "x": {
                "type": "number",
                "unit": {"system": "udunits", "code": "mm", "label": 123},
            }
        },
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_unit_annotations(schema, path="<root>", error_class=_ValidationError)
    assert "label" in str(exc_info.value)
    assert "must be a string" in str(exc_info.value)


@pytest.mark.unit
def test_validate_schema_declaration_threads_unit_check() -> None:
    """End-to-end: a `unit` annotation with a forbidden system surfaces
    via `validate_schema_declaration` (the public entry point each BC
    wrapper calls), with the caller's error class. This is the
    integration pin that prevents anyone accidentally bypassing the
    annotation check by going through the top-level entry."""
    schema = {
        "$schema": DRAFT_2020_12_URI,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "unit": {"system": "BOGUS", "code": "keV"},
            }
        },
    }
    with pytest.raises(_ValidationError) as exc_info:
        validate_schema_declaration(schema, error_class=_ValidationError)
    assert "not in CORA's allowed" in str(exc_info.value)


@pytest.mark.unit
def test_validate_schema_declaration_accepts_well_formed_unit_annotation() -> None:
    schema = {
        "$schema": DRAFT_2020_12_URI,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5.0,
                "maximum": 35.0,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "filter_material": {"type": "string"},
        },
    }
    validate_schema_declaration(schema, error_class=_ValidationError)
