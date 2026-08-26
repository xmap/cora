"""Integration tests: the descriptor preflight against a real softIOC subprocess.

The unit tier drives `preflight_read_channels` against a scripted fake, which proves
the reporting logic but cannot prove the command reaches a control system at
all. That gap matters more here than usual: this command's normal output on a
host with no route to the beamline is every row BAD, which is exactly what a
completely broken probe also prints. A green row has to be shown reachable
through the real `EpicsCaControlPort`, or the red ones carry no information.

Uses the shared `softioc` fixture (`tests/integration/conftest.py`): the
session-scoped `_pin_epics_env` autouse has already locked EPICS env vars to
the per-worker loopback port, so nothing here reaches a network.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest

from cora.api.descriptor_preflight import (
    descriptor_channels,
    preflight_read_channels,
    render_report,
)
from cora.infrastructure.control_port_route import ControlPortRoute
from cora.operation.adapters.control_port_config import build_control_port

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from cora.operation.ports.control_port import ControlPort


@pytest.fixture
async def control_port(softioc: str) -> AsyncIterator[ControlPort]:
    """A real CA-backed port routed at the softIOC's prefix, read-only, the
    same posture `main` builds."""
    port = build_control_port(
        [ControlPortRoute(prefix=softioc, substrate="epics_ca", is_simulated=True)],
        writes_enabled=False,
    )
    try:
        yield port
    finally:
        aclose = getattr(port, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()


def _descriptor(prefix: str) -> dict[str, Any]:
    """A synthetic descriptor exercising every address shape the walk
    supports, against records the softIOC actually serves."""
    return {
        "enclosures": [{"name": "TEST-A", "permit_signal": f"{prefix}long_value"}],
        "optics": {
            "stage": "source",
            "devices": [
                {"name": "Analog", "pv": f"{prefix}double_value"},
                {"name": "Selector", "pv": f"{prefix}enum_value"},
                {"name": "Trace", "pv": f"{prefix}waveform"},
                {
                    "name": "Slit",
                    "pv": {"x_in": f"{prefix}double_value", "y_top": f"{prefix}long_value"},
                },
                {"name": "Lens", "slot_labels_pv": [f"{prefix}string_value"]},
                {
                    "name": "Tower",
                    "pv": f"{prefix}long_value",
                    "constituents": [{"name": "Hexapod", "pv": f"{prefix}cam1:AcquireTime"}],
                },
            ],
        },
    }


async def test_preflight_reads_every_live_address_shape_against_a_real_ioc(
    control_port: ControlPort, softioc: str
) -> None:
    channels = descriptor_channels(_descriptor(softioc))
    report = await preflight_read_channels(control_port=control_port, channels=channels)

    assert not report.problem, [r.render() for r in report.readings if not r.ok]
    assert len(report.readings) == 9
    by_location = {r.channel.location: r for r in report.readings}
    assert by_location["Analog"].kind == "Scalar"
    assert by_location["Selector"].kind == "Categorical"
    assert by_location["Trace"].kind == "Array"
    assert by_location["Trace"].element_count is not None
    assert by_location["Hexapod"].ok
    assert by_location["TEST-A"].channel.field_name == "permit_signal"


async def test_preflight_reports_an_address_the_ioc_does_not_serve(
    control_port: ControlPort, softioc: str
) -> None:
    """The drift case this command exists for: a descriptor naming a record
    that is not there. The route matches, so this is a dead address, not a
    configuration gap."""
    raw = {
        "g": {
            "devices": [
                {"name": "Live", "pv": f"{softioc}double_value"},
                {"name": "Ghost", "pv": f"{softioc}no_such_record"},
            ]
        }
    }
    channels = descriptor_channels(raw)
    report = await preflight_read_channels(control_port=control_port, channels=channels)

    assert report.problem
    outcomes = {r.channel.location: (r.ok, r.connected) for r in report.readings}
    assert outcomes == {"Live": (True, True), "Ghost": (False, False)}
    text = "\n".join(render_report(report, path=softioc))  # type: ignore[arg-type]
    assert "1/2 channels read" in text


async def test_preflight_names_an_address_no_configured_route_covers(
    control_port: ControlPort, softioc: str
) -> None:
    """An address outside every route prefix is a CONTROL_PORT_ROUTES gap,
    and must not be reported as a beamline that failed to answer."""
    raw = {"g": {"devices": [{"name": "Elsewhere", "pv": "unrouted:m1"}]}}
    channels = descriptor_channels(raw)
    report = await preflight_read_channels(control_port=control_port, channels=channels)
    assert "CONTROL_PORT_ROUTES" in report.readings[0].detail


async def test_preflight_never_writes_to_the_ioc(control_port: ControlPort, softioc: str) -> None:
    """Read the value, run a full probe, read it again. The command's whole
    safety claim is that it changes nothing, and the claim is worth what a
    test of it is worth."""
    address = f"{softioc}double_value"
    before = await control_port.read(address)
    await preflight_read_channels(
        control_port=control_port, channels=descriptor_channels(_descriptor(softioc))
    )
    after = await control_port.read(address)
    assert before.value == after.value
