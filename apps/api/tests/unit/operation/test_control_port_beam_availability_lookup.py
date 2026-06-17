"""Unit tests for `ControlPortBeamAvailabilityLookup` (BEAM-1).

Covers the inverted `BeamBlockingM` polarity, the ACIS permit polarity,
the fail-closed mapping (disconnect / non-Good quality -> not-open +
`quality_ok=False`), and the unconfigured-PV no-gate default, all over
`InMemoryControlPort`.
"""

from datetime import UTC, datetime

import pytest

from cora.operation.adapters.control_port_beam_availability_lookup import (
    ControlPortBeamAvailabilityLookup,
)
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.ports.control_port import Reading

FES_PV = "FE:2BM:BeamBlockingM"
SBS_PV = "S02BM:SBS:BeamBlockingM"
PERMIT_PV = "SR-ACIS:2BM:FesPermitM"

ALL_PVS = {"fes": FES_PV, "sbs": SBS_PV, "fes_permit": PERMIT_PV}


def _scalar(value: object, *, quality: str = "Good") -> Reading:
    return Reading(
        value=value,
        kind="Scalar",
        quality=quality,  # type: ignore[arg-type]
        sampled_at=datetime(2026, 6, 17, tzinfo=UTC),
        quality_detail="",
    )


def _port_with(readings: dict[str, Reading]) -> InMemoryControlPort:
    port = InMemoryControlPort()
    for address, reading in readings.items():
        port.set_reading(address, reading)
    return port


@pytest.mark.unit
async def test_read_beam_availability_all_open_when_blocking_zero_and_permit_one() -> None:
    port = _port_with({FES_PV: _scalar(0), SBS_PV: _scalar(0), PERMIT_PV: _scalar(1)})
    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_open is True
    assert result.sbs_open is True
    assert result.fes_permit is True
    assert result.quality_ok is True


@pytest.mark.unit
async def test_read_beam_availability_fes_closed_when_blocking_nonzero() -> None:
    port = _port_with({FES_PV: _scalar(1), SBS_PV: _scalar(0), PERMIT_PV: _scalar(1)})
    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_open is False
    assert result.sbs_open is True
    assert result.quality_ok is True


@pytest.mark.unit
async def test_read_beam_availability_permit_denied_when_acis_zero() -> None:
    port = _port_with({FES_PV: _scalar(0), SBS_PV: _scalar(0), PERMIT_PV: _scalar(0)})
    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_permit is False
    assert result.quality_ok is True


@pytest.mark.unit
async def test_read_beam_availability_non_good_quality_fails_closed() -> None:
    port = _port_with(
        {
            FES_PV: _scalar(0, quality="Uncertain"),
            SBS_PV: _scalar(0),
            PERMIT_PV: _scalar(1),
        }
    )
    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_open is False  # cannot confirm open
    assert result.quality_ok is False


@pytest.mark.unit
async def test_read_beam_availability_disconnected_pv_fails_closed() -> None:
    port = _port_with({SBS_PV: _scalar(0), PERMIT_PV: _scalar(1)})  # no FES reading

    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_open is False
    assert result.quality_ok is False


@pytest.mark.unit
async def test_read_beam_availability_unconfigured_permit_does_not_gate() -> None:
    port = _port_with({FES_PV: _scalar(0), SBS_PV: _scalar(0)})

    lookup = ControlPortBeamAvailabilityLookup(
        control_port=port, beam_pvs={"fes": FES_PV, "sbs": SBS_PV}
    )

    result = await lookup.read_beam_availability()

    assert result.fes_open is True
    assert result.sbs_open is True
    assert result.fes_permit is True  # unconfigured -> not gating
    assert result.quality_ok is True


@pytest.mark.unit
async def test_read_beam_availability_non_integer_value_fails_closed() -> None:
    port = _port_with({FES_PV: _scalar("nan"), SBS_PV: _scalar(0), PERMIT_PV: _scalar(1)})
    lookup = ControlPortBeamAvailabilityLookup(control_port=port, beam_pvs=ALL_PVS)

    result = await lookup.read_beam_availability()

    assert result.fes_open is False
    assert result.quality_ok is False
