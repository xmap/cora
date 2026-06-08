"""Unit tests for `cora.shared.facility_code`.

Coverage:
  - happy path construction returns a frozen dataclass with the trimmed
    value installed.
  - trim semantics: leading + trailing whitespace stripped before length
    and regex checks; internal dashes preserved.
  - empty-after-trim and whitespace-only inputs raise with the ORIGINAL
    untrimmed value carried on the error.
  - over-length input raises with the ORIGINAL untrimmed value.
  - codepoint restriction: uppercase, underscore, dot, slash, space-only,
    and unicode-letter inputs all raise.
  - hash + equality + frozen-instance semantics work for use as dict keys.
  - `__str__` returns the trimmed value (callable from string-keyed
    in-memory adapters that key on the canonical value).
"""

from dataclasses import FrozenInstanceError

import pytest

from cora.shared.facility_code import (
    FACILITY_CODE_MAX_LENGTH,
    FacilityCode,
    InvalidFacilityCodeError,
)

# ---------- happy path + trim semantics ----------


@pytest.mark.unit
def test_facility_code_happy_path_lowercase_letters() -> None:
    assert FacilityCode("aps").value == "aps"


@pytest.mark.unit
def test_facility_code_accepts_digits() -> None:
    assert FacilityCode("aps2").value == "aps2"


@pytest.mark.unit
def test_facility_code_accepts_dash() -> None:
    assert FacilityCode("aps-2bm").value == "aps-2bm"


@pytest.mark.unit
def test_facility_code_happy_path_single_char() -> None:
    assert FacilityCode("a").value == "a"


@pytest.mark.unit
def test_facility_code_happy_path_at_max_length() -> None:
    payload = "a" * FACILITY_CODE_MAX_LENGTH
    assert FacilityCode(payload).value == payload


@pytest.mark.unit
def test_facility_code_trims_leading_and_trailing_whitespace() -> None:
    assert FacilityCode("  aps  ").value == "aps"


@pytest.mark.unit
def test_facility_code_trims_tabs_and_newlines() -> None:
    assert FacilityCode("\taps\n").value == "aps"


# ---------- rejection cases ----------


@pytest.mark.unit
def test_facility_code_empty_string_raises_with_original_value() -> None:
    with pytest.raises(InvalidFacilityCodeError) as excinfo:
        FacilityCode("")
    assert excinfo.value.value == ""


@pytest.mark.unit
def test_facility_code_whitespace_only_raises_with_original_untrimmed_value() -> None:
    with pytest.raises(InvalidFacilityCodeError) as excinfo:
        FacilityCode("   ")
    assert excinfo.value.value == "   "


@pytest.mark.unit
def test_facility_code_over_length_raises_with_original_untrimmed_value() -> None:
    over = "a" * (FACILITY_CODE_MAX_LENGTH + 1)
    with pytest.raises(InvalidFacilityCodeError) as excinfo:
        FacilityCode(over)
    assert excinfo.value.value == over


@pytest.mark.unit
def test_facility_code_rejects_uppercase_letters() -> None:
    with pytest.raises(InvalidFacilityCodeError) as excinfo:
        FacilityCode("APS")
    assert excinfo.value.value == "APS"


@pytest.mark.unit
def test_facility_code_rejects_mixed_case() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("Aps")


@pytest.mark.unit
def test_facility_code_rejects_underscore() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("aps_2bm")


@pytest.mark.unit
def test_facility_code_rejects_dot() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("aps.2bm")


@pytest.mark.unit
def test_facility_code_rejects_slash() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("aps/2bm")


@pytest.mark.unit
def test_facility_code_rejects_internal_space() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("aps 2bm")


@pytest.mark.unit
def test_facility_code_rejects_non_ascii_letter() -> None:
    with pytest.raises(InvalidFacilityCodeError):
        FacilityCode("apsé")


@pytest.mark.unit
def test_facility_code_over_length_after_trim_uses_trimmed_length_for_check() -> None:
    """Trim runs BEFORE length check, so padded-but-otherwise-valid inputs
    survive when the trimmed value fits the budget."""
    payload = "  " + ("a" * FACILITY_CODE_MAX_LENGTH) + "  "
    assert FacilityCode(payload).value == "a" * FACILITY_CODE_MAX_LENGTH


# ---------- dataclass dunders ----------


@pytest.mark.unit
def test_facility_code_equal_values_compare_equal() -> None:
    assert FacilityCode("aps") == FacilityCode("aps")


@pytest.mark.unit
def test_facility_code_different_values_compare_unequal() -> None:
    assert FacilityCode("aps") != FacilityCode("maxiv")


@pytest.mark.unit
def test_facility_code_trim_normalizes_for_equality() -> None:
    """Two `FacilityCode` values constructed from different padding compare
    equal because trim normalizes the stored value before equality."""
    assert FacilityCode("  aps  ") == FacilityCode("aps")


@pytest.mark.unit
def test_facility_code_hash_works_and_matches_equal_values() -> None:
    assert hash(FacilityCode("aps")) == hash(FacilityCode("aps"))


@pytest.mark.unit
def test_facility_code_instances_usable_as_dict_keys() -> None:
    d = {FacilityCode("aps"): 1, FacilityCode("maxiv"): 2}
    assert d[FacilityCode("aps")] == 1
    assert d[FacilityCode("maxiv")] == 2


@pytest.mark.unit
def test_facility_code_frozen_assignment_raises_frozen_instance_error() -> None:
    instance = FacilityCode("aps")
    with pytest.raises(FrozenInstanceError):
        instance.value = "mut"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.unit
def test_facility_code_str_returns_trimmed_value() -> None:
    assert str(FacilityCode("  aps  ")) == "aps"
