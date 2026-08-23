"""Unit tests for `binary_code`.

Consolidates the parametrized coverage that used to live independently
in each of the three call sites this hoists (`_enclosure_permit_observer`,
`control_port_beam_availability_lookup`, `_capture_observer`) plus the
fourth (`_bleps_supply_observer`) that triggered the hoist. Each site's
own test file keeps its consumer-level tests (quality floors, polarity,
the mapped domain string); this file owns only the pure 0/1 decode.
"""

import pytest

from cora.shared.binary_signal import binary_code

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [1, 1.0, True, "1"])
def test_recognized_one_values_decode_to_one(value: object) -> None:
    assert binary_code(value) == 1


@pytest.mark.parametrize("value", [0, 0.0, False, "0"])
def test_recognized_zero_values_decode_to_zero(value: object) -> None:
    assert binary_code(value) == 0


@pytest.mark.parametrize("label", ["ON", "TRUE", "YES"])
def test_conventional_one_labels_decode_to_one(label: str) -> None:
    assert binary_code(label) == 1


@pytest.mark.parametrize("label", ["OFF", "FALSE", "NO"])
def test_conventional_zero_labels_decode_to_zero(label: str) -> None:
    assert binary_code(label) == 0


def test_label_matching_ignores_case_and_padding() -> None:
    assert binary_code(" on ") == 1
    assert binary_code("Off") == 0


@pytest.mark.parametrize("value", ["SEARCHED", "TRIP", "OK", "SEARCHING", None, object()])
def test_unrecognized_values_decode_to_none(value: object) -> None:
    assert binary_code(value) is None


def test_out_of_range_numeric_decodes_to_none() -> None:
    """A stray 2 is not a third state; it fails closed like any other
    unbelievable reading rather than being trusted and compared unequal.
    """
    assert binary_code(2) is None
    assert binary_code("2") is None


def test_non_integral_string_decodes_to_none() -> None:
    assert binary_code("1.5") is None
    assert binary_code("") is None
