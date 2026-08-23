"""Unit tests for `binary_code`.

Consolidates the parametrized coverage that used to live independently
in each of the three call sites this hoists (`_enclosure_permit_observer`,
`control_port_beam_availability_lookup`, `_capture_observer`) plus the
fourth (`_bleps_supply_observer`) that triggered the hoist. Each site's
own test file keeps its consumer-level tests (quality floors, polarity,
the mapped domain string); this file owns only the pure 0/1 decode.

Two axes are covered: the ordinal path (what an adapter supplies for an
enum reading, and what decides whenever it is present) and the label
path (the fallback for a reading that carries no ordinal).
"""

import pytest

from cora.shared.binary_signal import binary_code

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [1, 1.0, True, "1"])
def test_recognized_one_values_decode_to_one(value: object) -> None:
    assert binary_code(value, ordinal=None) == 1


@pytest.mark.parametrize("value", [0, 0.0, False, "0"])
def test_recognized_zero_values_decode_to_zero(value: object) -> None:
    assert binary_code(value, ordinal=None) == 0


@pytest.mark.parametrize("label", ["ON", "TRUE", "YES"])
def test_conventional_one_labels_decode_to_one(label: str) -> None:
    assert binary_code(label, ordinal=None) == 1


@pytest.mark.parametrize("label", ["OFF", "FALSE", "NO"])
def test_conventional_zero_labels_decode_to_zero(label: str) -> None:
    assert binary_code(label, ordinal=None) == 0


def test_label_matching_ignores_case_and_padding() -> None:
    assert binary_code(" on ", ordinal=None) == 1
    assert binary_code("Off", ordinal=None) == 0


@pytest.mark.parametrize("value", ["SEARCHED", "TRIP", "OK", "SEARCHING", None, object()])
def test_unrecognized_values_decode_to_none(value: object) -> None:
    assert binary_code(value, ordinal=None) is None


def test_out_of_range_numeric_decodes_to_none() -> None:
    """A stray 2 is not a third state; it fails closed like any other
    unbelievable reading rather than being trusted and compared unequal.
    """
    assert binary_code(2, ordinal=None) is None
    assert binary_code("2", ordinal=None) is None


def test_non_integral_string_decodes_to_none() -> None:
    assert binary_code("1.5", ordinal=None) is None
    assert binary_code("", ordinal=None) is None


@pytest.mark.parametrize("value", [0.4, 1.9, -0.5, 0.0001])
def test_non_integral_float_decodes_to_none(value: float) -> None:
    """A fractional reading on a two-state signal must not truncate.

    `int(0.4)` is 0, and 0 is a CONFIRMED state to every consumer: on
    the beam shutters, whose polarity is inverted, it means "open". So
    truncation here is a fail-OPEN, not a rounding nicety. The beam
    lookup has carried its own guard for this since it shipped; this
    pins the same floor for the four consumers that never had one.
    """
    assert binary_code(value, ordinal=None) is None


def test_integral_floats_still_decode() -> None:
    """The guard rejects FRACTIONS, not the float type.

    An `ai` record legitimately reports 0.0 / 1.0 for a flag, and that
    reading is unambiguous.
    """
    assert binary_code(0.0, ordinal=None) == 0
    assert binary_code(1.0, ordinal=None) == 1


def test_a_present_ordinal_decides_the_code() -> None:
    assert binary_code("anything at all", ordinal=1) == 1
    assert binary_code("anything at all", ordinal=0) == 0


def test_ordinal_out_of_range_decodes_to_none() -> None:
    """An mbbi sitting in its third state is not a two-state answer.

    Failing closed here matters more than for a stray numeric `value`:
    an ordinal is authoritative, so trusting an out-of-range one would
    be trusting the wrong record with full confidence.

    Every label here is one the FALLBACK path would happily decode, so
    the assertion can only pass if the out-of-range ordinal short-
    circuits it. Written that way deliberately: the first version used
    labels like `"Moving"` that the fallback also rejects, so it
    returned `None` for the wrong reason and stayed green when the
    ordinal branch was deleted.
    """
    assert binary_code("ON", ordinal=2) is None
    assert binary_code("OFF", ordinal=7) is None
    assert binary_code("YES", ordinal=-1) is None


def test_ordinal_wins_over_a_label_that_says_otherwise() -> None:
    """The two halves disagreeing is the whole reason the ordinal exists.

    A facility is free to relabel state 1 to anything, including a word
    whose plain reading is the opposite. The index is what CORA acts on.
    """
    assert binary_code("OFF", ordinal=1) == 1
    assert binary_code("ON", ordinal=0) == 0


@pytest.mark.parametrize(
    ("label", "ordinal", "expected"),
    [
        ("NO_FAULT", 0, 0),
        ("TRIP", 1, 1),
        ("", 0, 0),
        ("Present", 1, 1),
    ],
)
def test_real_2bm_bleps_labels_decode_by_ordinal(label: str, ordinal: int, expected: int) -> None:
    """The exact pairs the deployed 2-BM BLEPS IOC publishes.

    Measured on arcturus 2026-08-23 from `bleps.substitutions`: trips and
    warnings are `NO_FAULT` / `TRIP`, faults and the comms flag are
    `""` / `Present`. Every one of these four is outside the conventional
    label set, so this is the case that reads nothing without the
    ordinal. `""` is the sharpest: it is the HEALTHY state of the
    system-wide comms flag, so failing to read it suppressed the entire
    observer, not just one channel.
    """
    assert binary_code(label, ordinal=ordinal) == expected


@pytest.mark.parametrize("label", ["NO_FAULT", "TRIP", "", "Present"])
def test_real_2bm_bleps_labels_are_undecodable_without_an_ordinal(label: str) -> None:
    """The negative half of the pair above, pinning WHY the ordinal is load-bearing.

    If a future edit taught the shared label set these words, this test
    would fail and say so. That is the point: the fix is to read the
    index, not to accumulate one facility's vocabulary in `cora.shared`.
    """
    assert binary_code(label, ordinal=None) is None
