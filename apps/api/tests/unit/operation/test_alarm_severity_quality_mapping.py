"""Unit-tier pin on the EPICS alarm-severity to `Quality` trichotomy.

The three EPICS adapters (`EpicsCaControlPort`, `EpicsPvaControlPort`,
`CaprotoControlPort`) each hold their own severity table, because each
receives severity in a substrate-native shape (aioca int, p4p int,
caproto `AlarmSeverity`). Three tables mean three chances to drift,
and the integration tier can only reach them with a live softIOC. This
file pins all three against one expectation table so a drift shows up
in the fast lane.

The mapping under test: NO_ALARM is Good, MINOR and MAJOR are
Uncertain, INVALID is Bad. EPICS separates "the value is fine but the
process it describes is in alarm" (MINOR / MAJOR) from "the value
itself is not trustworthy" (INVALID); only the latter is Bad. An
unknown severity also falls to Bad, since a severity CORA cannot name
is a reading CORA cannot vouch for.
"""

import pytest
from caproto import AlarmSeverity

from cora.operation.adapters.caproto_control_port import (
    _quality_for as caproto_quality_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_ca_control_port import (
    _quality_for as ca_quality_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.adapters.epics_pva_control_port import (
    _quality_for as pva_quality_for,  # pyright: ignore[reportPrivateUsage]
)
from cora.operation.ports.control_port import Quality

_EXPECTED: tuple[tuple[int, Quality], ...] = (
    (AlarmSeverity.NO_ALARM, "Good"),
    (AlarmSeverity.MINOR_ALARM, "Uncertain"),
    (AlarmSeverity.MAJOR_ALARM, "Uncertain"),
    (AlarmSeverity.INVALID_ALARM, "Bad"),
)


@pytest.mark.unit
@pytest.mark.parametrize(("severity", "expected"), _EXPECTED)
def test_epics_ca_maps_severity_to_expected_quality(severity: int, expected: Quality) -> None:
    assert ca_quality_for(severity) == expected


@pytest.mark.unit
@pytest.mark.parametrize(("severity", "expected"), _EXPECTED)
def test_epics_pva_maps_severity_to_expected_quality(severity: int, expected: Quality) -> None:
    assert pva_quality_for(severity) == expected


@pytest.mark.unit
@pytest.mark.parametrize(("severity", "expected"), _EXPECTED)
def test_caproto_maps_severity_to_expected_quality(severity: int, expected: Quality) -> None:
    assert caproto_quality_for(AlarmSeverity(severity)) == expected


@pytest.mark.unit
@pytest.mark.parametrize("severity", [-1, 4, 99])
def test_unknown_severity_falls_to_bad_on_every_adapter(severity: int) -> None:
    """A severity outside the EPICS 0-3 range is a reading CORA cannot vouch for."""
    assert ca_quality_for(severity) == "Bad"
    assert pva_quality_for(severity) == "Bad"
    assert caproto_quality_for(severity) == "Bad"


@pytest.mark.unit
def test_the_three_adapters_agree_on_every_epics_severity() -> None:
    """Cross-adapter symmetry: same severity in, same quality out."""
    for severity in range(4):
        assert (
            ca_quality_for(severity)
            == pva_quality_for(severity)
            == caproto_quality_for(AlarmSeverity(severity))
        )
