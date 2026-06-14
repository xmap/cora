"""Unit tests for the `ControlPort` factory + route shape.

Covers:

  - empty routes -> InMemoryControlPort (legacy default)
  - in_memory route -> ControlPortRegistry routing the prefix to
    an InMemoryControlPort
  - epics_ca route -> ControlPortRegistry routing the prefix to
    an EpicsCaControlPort (constructed; not exercised against EPICS)
  - epics_pva route -> ControlPortRegistry routing the prefix to
    an EpicsPvaControlPort
  - mixed routes -> registry picks the right adapter per prefix
  - route Pydantic validation: empty prefix rejected, unknown
    substrate rejected, extra fields rejected
"""

import pytest
from pydantic import ValidationError

from cora.infrastructure.control_port_route import ControlPortRoute
from cora.operation.adapters.control_port_config import build_control_port
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort


@pytest.mark.unit
def test_build_control_port_with_empty_routes_returns_in_memory_port() -> None:
    port = build_control_port([])
    assert isinstance(port, InMemoryControlPort)


@pytest.mark.unit
def test_build_control_port_with_single_in_memory_route_returns_registry() -> None:
    port = build_control_port([ControlPortRoute(prefix="2bma:", substrate="in_memory")])
    assert isinstance(port, ControlPortRegistry)
    routed = port.route("2bma:rot:val")
    assert isinstance(routed, InMemoryControlPort)


@pytest.mark.unit
def test_build_control_port_with_epics_ca_route_constructs_ca_adapter() -> None:
    port = build_control_port([ControlPortRoute(prefix="2bma:", substrate="epics_ca")])
    assert isinstance(port, ControlPortRegistry)
    routed = port.route("2bma:rot:val")
    assert isinstance(routed, EpicsCaControlPort)


@pytest.mark.unit
def test_build_control_port_with_epics_pva_route_constructs_pva_adapter() -> None:
    port = build_control_port([ControlPortRoute(prefix="2bma:cam:image", substrate="epics_pva")])
    assert isinstance(port, ControlPortRegistry)
    routed = port.route("2bma:cam:image:data")
    assert isinstance(routed, EpicsPvaControlPort)


@pytest.mark.unit
def test_build_control_port_with_mixed_routes_picks_right_adapter_per_prefix() -> None:
    """Mixed 2-BM deployment shape: general CA, specific PVA for image PVs."""
    port = build_control_port(
        [
            ControlPortRoute(prefix="2bma:cam1:image", substrate="epics_pva"),
            ControlPortRoute(prefix="2bma:", substrate="epics_ca"),
        ]
    )
    assert isinstance(port, ControlPortRegistry)
    # Specific prefix wins for image addresses (longest-prefix-match).
    assert isinstance(port.route("2bma:cam1:image:data"), EpicsPvaControlPort)
    # The general prefix catches every other 2bma: address.
    assert isinstance(port.route("2bma:rot:val"), EpicsCaControlPort)


@pytest.mark.unit
def test_control_port_route_rejects_empty_prefix() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute(prefix="", substrate="in_memory")


@pytest.mark.unit
def test_control_port_route_rejects_unknown_substrate() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute.model_validate({"prefix": "x:", "substrate": "tango"})


@pytest.mark.unit
def test_control_port_route_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute.model_validate(
            {"prefix": "x:", "substrate": "in_memory", "timeout_s": 5.0}
        )


@pytest.mark.unit
async def test_build_control_port_returned_registry_supports_aclose() -> None:
    """The registry's aclose() fans out to every constructed adapter."""
    port = build_control_port([ControlPortRoute(prefix="x:", substrate="in_memory")])
    assert isinstance(port, ControlPortRegistry)
    await port.aclose()  # no-op for InMemoryControlPort; should not raise


@pytest.mark.unit
def test_control_port_route_is_simulated_defaults_false() -> None:
    assert ControlPortRoute(prefix="2bma:", substrate="epics_ca").is_simulated is False


@pytest.mark.unit
def test_build_control_port_threads_is_simulated_flag_to_registry() -> None:
    """A soft-IOC deployment tags its CA route simulated; the flag survives wiring.

    The transport is the production `epics_ca` adapter (a soft IOC speaks
    real Channel Access), so only the declared `is_simulated` flag tells
    the gate this route is a simulator.
    """
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="epics_ca", is_simulated=True)]
    )
    assert isinstance(port, ControlPortRegistry)
    assert port.route_is_simulated("2bma:rot:val") is True


@pytest.mark.unit
def test_build_control_port_mixed_simulated_and_physical_routes() -> None:
    """A simulated sub-band carved out of an otherwise physical crate."""
    port = build_control_port(
        [
            ControlPortRoute(prefix="2bma:sim:", substrate="in_memory", is_simulated=True),
            ControlPortRoute(prefix="2bma:", substrate="epics_ca", is_simulated=False),
        ]
    )
    assert isinstance(port, ControlPortRegistry)
    assert port.route_is_simulated("2bma:sim:rot") is True
    assert port.route_is_simulated("2bma:rot:val") is False
