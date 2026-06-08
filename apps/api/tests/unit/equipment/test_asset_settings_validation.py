"""Unit tests for the Asset.settings cross-Family validator.

`validate_settings_against_families`: union schemas + strict /
permissive mode + true-type-conflict detection.

The companion `merge_patch` tests moved to
`tests/unit/test_json_merge_patch.py` when the function hoisted to
`cora.shared.json_merge_patch`.
"""

from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset.settings_validation import (
    validate_settings_against_families,
)
from cora.equipment.aggregates.asset.state import InvalidAssetSettingsError
from cora.equipment.aggregates.family.state import (
    Family,
    FamilyName,
    FamilyStatus,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability(*, settings_schema: dict[str, Any] | None) -> Family:
    return Family(
        id=uuid4(),
        name=FamilyName("Tomography"),
        status=FamilyStatus.DEFINED,
        settings_schema=settings_schema,
    )


def _schema(**body: Any) -> dict[str, Any]:
    return {"$schema": _DRAFT, **body}


# ---------- validate_settings_against_families ----------


@pytest.mark.unit
def test_validate_no_capabilities_no_settings_passes() -> None:
    """Trivial case: nothing to validate against, nothing to validate."""
    validate_settings_against_families({}, [])


@pytest.mark.unit
def test_validate_no_capabilities_non_empty_settings_rejects() -> None:
    """Asset with no Capabilities cannot have settings (no schema source)."""
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_families({"x": 1}, [])
    assert "no assigned Capabilities" in exc_info.value.reason


@pytest.mark.unit
def test_validate_passes_when_all_keys_match_single_schema() -> None:
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "energy": {
                    "type": "number",
                    "minimum": 5,
                    "unit": {"system": "udunits", "code": "keV"},
                }
            },
        )
    )
    validate_settings_against_families({"energy": 30}, [cap])


@pytest.mark.unit
def test_validate_rejects_constraint_violation() -> None:
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "energy": {
                    "type": "number",
                    "minimum": 5,
                    "unit": {"system": "udunits", "code": "keV"},
                }
            },
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_families({"energy": 1}, [cap])
    assert "energy" in exc_info.value.reason


@pytest.mark.unit
def test_validate_rejects_orphan_key_when_all_capabilities_have_schemas() -> None:
    """STRICT mode: if every Family declares a schema, unknown keys reject."""
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_families({"energy": 30, "unknown_key": "x"}, [cap])
    assert "unknown_key" in exc_info.value.reason


@pytest.mark.unit
def test_validate_strict_when_one_capability_is_schemaless_rejects_unknown_key() -> None:
    """Strict (audit reversal): a schemaless Family is a
    no-op in the union; only DECLARED schemas constrain the
    allowed-keys set. An unknown key (`vendor_specific` not declared
    by any declared schema) is rejected even when at least one
    Family is schemaless. Originally permissive ("degrade
    gracefully"), reversed for consistency with the
    strict-when-no-schema reversal."""
    declared = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
        )
    )
    schemaless = _capability(settings_schema=None)
    with pytest.raises(InvalidAssetSettingsError):
        validate_settings_against_families(
            {"energy": 30, "vendor_specific": "x"},
            [declared, schemaless],
        )


@pytest.mark.unit
def test_validate_passes_when_one_capability_is_schemaless_and_keys_are_declared() -> None:
    """Strict mode still accepts declared keys when a sibling
    Family is schemaless — the schemaless one contributes nothing
    but doesn't block the declared keys."""
    declared = _capability(
        settings_schema=_schema(
            type="object",
            properties={"energy": {"type": "number", "unit": {"system": "udunits", "code": "keV"}}},
        )
    )
    schemaless = _capability(settings_schema=None)
    validate_settings_against_families(
        {"energy": 30},
        [declared, schemaless],
    )


@pytest.mark.unit
def test_validate_rejects_when_all_capabilities_are_schemaless_with_settings() -> None:
    """ALL-SCHEMALESS mode: when every Family is schemaless and
    settings is non-empty, reject with a clear message instructing
    the operator to declare a schema on at least one Family
    (an empty `{}` is valid). Mirrors the NO-CAPABILITIES posture
    and the 6g-b/c "Method declares no schema" rejection."""
    schemaless_a = _capability(settings_schema=None)
    schemaless_b = _capability(settings_schema=None)
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_families(
            {"some_key": "some_value"},
            [schemaless_a, schemaless_b],
        )
    assert "every assigned Family is schemaless" in exc_info.value.reason
    assert "'some_key'" in exc_info.value.reason


@pytest.mark.unit
def test_validate_passes_when_all_capabilities_are_schemaless_with_empty_settings() -> None:
    """ALL-SCHEMALESS mode allows empty settings (no contract, no
    values, no conflict)."""
    schemaless = _capability(settings_schema=None)
    validate_settings_against_families({}, [schemaless])


@pytest.mark.unit
def test_validate_passes_when_capability_declares_empty_schema_and_settings_empty() -> None:
    """Operators can declare `settings_schema={}` to explicitly say
    'this Family has no settings to constrain'. With non-empty
    settings, the empty schema rejects unknown keys (jsonschema-rs);
    with empty settings, validation passes."""
    explicit_empty = _capability(settings_schema=_schema())  # {"$schema": DRAFT}, no properties
    validate_settings_against_families({}, [explicit_empty])


@pytest.mark.unit
def test_validate_unions_keys_across_two_capabilities() -> None:
    cap_a = _capability(
        settings_schema=_schema(type="object", properties={"x": {"type": "number"}})
    )
    cap_b = _capability(
        settings_schema=_schema(type="object", properties={"y": {"type": "string"}})
    )
    validate_settings_against_families({"x": 1, "y": "ok"}, [cap_a, cap_b])


@pytest.mark.unit
def test_validate_intersects_constraints_for_shared_key() -> None:
    """Two Capabilities both declare `temperature` as number with
    different minimums; allOf intersection makes the higher minimum
    binding."""
    cap_a = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "temperature": {
                    "type": "number",
                    "minimum": 5,
                    "unit": {"system": "udunits", "code": "degC"},
                }
            },
        )
    )
    cap_b = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "temperature": {
                    "type": "number",
                    "minimum": 20,
                    "unit": {"system": "udunits", "code": "degC"},
                }
            },
        )
    )
    # 25 satisfies both
    validate_settings_against_families({"temperature": 25}, [cap_a, cap_b])
    # 10 satisfies cap_a but not cap_b -> reject
    with pytest.raises(InvalidAssetSettingsError):
        validate_settings_against_families({"temperature": 10}, [cap_a, cap_b])


@pytest.mark.unit
def test_validate_rejects_true_type_conflict_across_capabilities() -> None:
    """Two Capabilities declare the same key with incompatible types —
    no value can satisfy both; the validator names both Capabilities."""
    cap_a = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "temperature": {
                    "type": "number",
                    "unit": {"system": "udunits", "code": "degC"},
                }
            },
        )
    )
    cap_b = _capability(
        settings_schema=_schema(
            type="object",
            properties={"temperature": {"type": "string"}},
        )
    )
    with pytest.raises(InvalidAssetSettingsError) as exc_info:
        validate_settings_against_families({"temperature": 25}, [cap_a, cap_b])
    assert "incompatible types" in exc_info.value.reason
    assert "temperature" in exc_info.value.reason
    # Both Family ids surface in the diagnostic.
    assert str(cap_a.id) in exc_info.value.reason
    assert str(cap_b.id) in exc_info.value.reason


@pytest.mark.unit
def test_validate_empty_settings_passes_with_strict_schemas() -> None:
    """Removing all settings (empty dict) is always valid: no value is
    constrained because none is provided. Useful for the 'reset to
    defaults' cleanup path via merge_patch with all-null."""
    cap = _capability(
        settings_schema=_schema(
            type="object",
            properties={
                "energy": {
                    "type": "number",
                    "minimum": 5,
                    "unit": {"system": "udunits", "code": "keV"},
                }
            },
            required=[],  # leave required empty so empty dict passes
        )
    )
    validate_settings_against_families({}, [cap])
