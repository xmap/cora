"""Unit tests for the `ControlPort` factory + route shape.

Covers:

  - empty routes -> InMemoryControlPort (legacy default)
  - in_memory route -> ControlPortRegistry routing the prefix to
    an InMemoryControlPort
  - epics_ca route -> ControlPortRegistry routing the prefix to
    an EpicsCaControlPort (constructed; not exercised against EPICS)
  - epics_pva route -> ControlPortRegistry routing the prefix to
    an EpicsPvaControlPort
  - tango route -> ControlPortRegistry routing the prefix to a
    TangoControlPort (probe neutralised; PyTango absent in base env)
  - mixed routes -> registry picks the right adapter per prefix
  - route Pydantic validation: empty prefix rejected, unknown
    substrate rejected, extra fields rejected
  - writes_enabled=False wraps every route so writes refuse, with no
    per-substrate exemption; per-route read_only wraps only its route

Every routing test passes `writes_enabled=True` so it observes the
naked adapter: the write posture is orthogonal to which adapter a
prefix resolves to, and stating it keeps the two concerns separable.
"""

import pytest
from pydantic import ValidationError

from cora.infrastructure.control_port_route import ControlPortRoute
from cora.operation.adapters.control_port_config import build_control_port
from cora.operation.adapters.control_port_registry import ControlPortRegistry
from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.read_only_control_port import ReadOnlyControlPort
from cora.operation.adapters.tango_control_port import TangoControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlWritesDisabledError,
    NoAdapterForAddressError,
)


def _no_tango_probe(_substrate: str) -> None:
    """Neutralised `require_tango`: PyTango is absent in the base test env."""


@pytest.mark.unit
def test_build_control_port_with_empty_routes_returns_in_memory_port() -> None:
    port = build_control_port([], writes_enabled=True)
    assert isinstance(port, InMemoryControlPort)


@pytest.mark.unit
async def test_build_control_port_with_single_in_memory_route_returns_registry() -> None:
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="in_memory")], writes_enabled=True
    )
    assert isinstance(port, ControlPortRegistry)
    # in_memory routes ride the registry's str-port wrapper (an internal
    # detail), so assert behaviour rather than the wrapper type: a matched
    # address dispatches to the in-memory adapter, which raises
    # ControlNotConnectedError (its response for an unseeded address), NOT the
    # NoAdapterForAddressError an unrouted prefix would raise.
    with pytest.raises(ControlNotConnectedError):
        await port.read("2bma:rot:val")
    with pytest.raises(NoAdapterForAddressError):
        await port.read("7bma:rot:val")


@pytest.mark.unit
def test_build_control_port_with_epics_ca_route_constructs_ca_adapter() -> None:
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="epics_ca")], writes_enabled=True
    )
    assert isinstance(port, ControlPortRegistry)
    routed = port.route("2bma:rot:val")
    assert isinstance(routed, EpicsCaControlPort)


@pytest.mark.unit
def test_build_control_port_with_epics_pva_route_constructs_pva_adapter() -> None:
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:cam:image", substrate="epics_pva")], writes_enabled=True
    )
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
        ],
        writes_enabled=True,
    )
    assert isinstance(port, ControlPortRegistry)
    # Specific prefix wins for image addresses (longest-prefix-match).
    assert isinstance(port.route("2bma:cam1:image:data"), EpicsPvaControlPort)
    # The general prefix catches every other 2bma: address.
    assert isinstance(port.route("2bma:rot:val"), EpicsCaControlPort)


@pytest.mark.unit
def test_build_control_port_with_tango_route_constructs_tango_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `tango` route builds a `TangoControlPort`.

    The adapter probes PyTango importability at construction; PyTango is not
    installed in the base test environment, so the probe is neutralised here
    to exercise the factory arm rather than the missing-extra path (that path
    is covered by `test_require_tango_raises_value_error_when_pytango_absent`).
    """
    monkeypatch.setattr(
        "cora.operation.adapters.tango_control_port.require_tango",
        _no_tango_probe,
    )
    port = build_control_port(
        [ControlPortRoute(prefix="id19/", substrate="tango")], writes_enabled=True
    )
    assert isinstance(port, ControlPortRegistry)
    routed = port.route("id19/bsh/1/state")
    assert isinstance(routed, TangoControlPort)


@pytest.mark.unit
def test_control_port_route_rejects_empty_prefix() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute(prefix="", substrate="in_memory")


@pytest.mark.unit
def test_control_port_route_rejects_unknown_substrate() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute.model_validate({"prefix": "x:", "substrate": "opc_ua"})


@pytest.mark.unit
def test_control_port_route_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ControlPortRoute.model_validate(
            {"prefix": "x:", "substrate": "in_memory", "timeout_s": 5.0}
        )


@pytest.mark.unit
async def test_build_control_port_returned_registry_supports_aclose() -> None:
    """The registry's aclose() fans out to every constructed adapter."""
    port = build_control_port(
        [ControlPortRoute(prefix="x:", substrate="in_memory")], writes_enabled=True
    )
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
        [ControlPortRoute(prefix="2bma:", substrate="epics_ca", is_simulated=True)],
        writes_enabled=True,
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
        ],
        writes_enabled=True,
    )
    assert isinstance(port, ControlPortRegistry)
    assert port.route_is_simulated("2bma:sim:rot") is True
    assert port.route_is_simulated("2bma:rot:val") is False


@pytest.mark.unit
def test_control_port_route_read_only_defaults_false() -> None:
    assert ControlPortRoute(prefix="2bma:", substrate="epics_ca").read_only is False


@pytest.mark.unit
async def test_build_control_port_writes_disabled_refuses_write_on_every_route() -> None:
    """The deployment switch is the observe-only safety mechanism.

    No route declared `read_only`; the switch alone must still refuse, and
    it must refuse on a real substrate route (the typed guard path), not
    only the in-memory one.
    """
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="epics_ca")], writes_enabled=False
    )
    with pytest.raises(ControlWritesDisabledError) as excinfo:
        await port.write("2bma:rot:val", 90.0)
    assert excinfo.value.address == "2bma:rot:val"
    assert excinfo.value.scope == "deployment"
    # Attribution follows scope: the route did not carry this refusal.
    assert excinfo.value.prefix is None


@pytest.mark.unit
async def test_build_control_port_writes_disabled_refuses_write_on_in_memory_route() -> None:
    """The str-surface guard path (in_memory) refuses too, through the shim."""
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="in_memory")], writes_enabled=False
    )
    with pytest.raises(ControlWritesDisabledError):
        await port.write("2bma:rot:val", 90.0)


@pytest.mark.unit
async def test_build_control_port_writes_disabled_still_allows_read() -> None:
    """Observe-only must still observe. The read reaches the inner adapter,
    surfacing that adapter's own not-connected error rather than the guard's
    refusal, which it could only do by passing through."""
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="in_memory")], writes_enabled=False
    )
    with pytest.raises(ControlNotConnectedError):
        await port.read("2bma:rot:val")


@pytest.mark.unit
def test_build_control_port_writes_disabled_grants_no_substrate_exemption() -> None:
    """in_memory is wrapped too: an exemption is a partial application."""
    port = build_control_port([], writes_enabled=False)
    assert isinstance(port, ReadOnlyControlPort)


@pytest.mark.unit
async def test_build_control_port_read_only_route_refuses_within_writable_deployment() -> None:
    """Per-route expressiveness: drive the stage, never the shutter."""
    port = build_control_port(
        [
            ControlPortRoute(prefix="2bma:shutter:", substrate="in_memory", read_only=True),
            ControlPortRoute(prefix="2bma:", substrate="in_memory"),
        ],
        writes_enabled=True,
    )
    assert isinstance(port, ControlPortRegistry)
    with pytest.raises(ControlWritesDisabledError) as excinfo:
        await port.write("2bma:shutter:open", 1)
    assert excinfo.value.scope == "route"
    assert excinfo.value.prefix == "2bma:shutter:"
    # The sibling route in the same registry stays writable: the write
    # reaches the in-memory adapter and raises ITS not-connected error
    # (the address was never seeded), NOT the guard's refusal. That it is
    # not ControlWritesDisabledError is the point.
    with pytest.raises(ControlNotConnectedError):
        await port.write("2bma:rot:val", 90.0)


@pytest.mark.unit
def test_build_control_port_read_only_route_preserves_registry_provenance() -> None:
    """The guard wraps BELOW the registry, so route_is_simulated survives.

    Wrapping the registry itself would hide this from the Conductor's
    `_ActuationObserver` getattr and silently disable the Dataset
    provenance gate.
    """
    port = build_control_port(
        [ControlPortRoute(prefix="2bma:", substrate="epics_ca", is_simulated=True, read_only=True)],
        writes_enabled=True,
    )
    assert isinstance(port, ControlPortRegistry)
    assert port.route_is_simulated("2bma:rot:val") is True


@pytest.mark.unit
def test_build_control_port_rejects_duplicate_prefixes() -> None:
    """Last-wins registration would silently discard a read_only declaration."""
    with pytest.raises(ValueError, match="more than once"):
        build_control_port(
            [
                ControlPortRoute(prefix="2bma:", substrate="in_memory", read_only=True),
                ControlPortRoute(prefix="2bma:", substrate="in_memory"),
            ],
            writes_enabled=True,
        )
