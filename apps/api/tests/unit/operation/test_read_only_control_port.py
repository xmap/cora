"""Unit tests for the `ReadOnlyControlPort` + `ReadOnlySubstratePort` guards.

Covers both surfaces #568 left the registry with:

  - write refuses, carrying address + scope + prefix (the typed guard
    carries `str(address)`)
  - refusal happens before the inner adapter is touched at all
  - read / subscribe still reach the inner adapter (observe-only
    must still observe)
  - aclose delegates (the registry skips adapters lacking it, so a
    missing delegation leaks every wrapped EPICS connection)
  - aclose tolerates an inner adapter with no aclose
  - the str guard satisfies the ControlPort protocol
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.adapters.read_only_control_port import (
    ReadOnlyControlPort,
    ReadOnlySubstratePort,
)
from cora.operation.ports.control_address import ControlAddress, InMemoryAddress
from cora.operation.ports.control_port import (
    ControlPort,
    ControlWritesDisabledError,
    Measurement,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _RecordingPort:
    """Inner adapter that records whether anything reached it."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, Any]] = []
        self.reads: list[str] = []
        self.subscribes: list[str] = []
        self.closed = False
        self._seeded = InMemoryControlPort()

    def seed(self, address: str, value: float = 45.0) -> None:
        self._seeded.set_reading(
            address,
            Measurement(
                value=value,
                kind="Scalar",
                quality="Good",
                produced_at=datetime(2026, 7, 16, tzinfo=UTC),
            ),
        )

    async def read(self, address: str) -> Measurement:
        self.reads.append(address)
        return await self._seeded.read(address)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        self.writes.append((address, value))

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        self.subscribes.append(address)
        return self._seeded.subscribe(address)

    async def aclose(self) -> None:
        self.closed = True


class _NoCloseCarrier:
    """Inner adapter with no aclose, mirroring a bare test double."""

    async def read(self, address: str) -> Measurement:
        return await InMemoryControlPort().read(address)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        raise AssertionError("guard must refuse before reaching the inner adapter")

    def subscribe(self, address: str) -> AsyncIterator[Measurement]:
        return InMemoryControlPort().subscribe(address)


@pytest.mark.unit
async def test_read_only_control_port_write_refuses_with_deployment_scope() -> None:
    port = ReadOnlyControlPort(_RecordingPort(), scope="deployment")
    with pytest.raises(ControlWritesDisabledError) as excinfo:
        await port.write("2bma:rot:val", 90.0)
    assert excinfo.value.address == "2bma:rot:val"
    assert excinfo.value.scope == "deployment"
    assert excinfo.value.prefix is None
    assert "deployment-wide" in str(excinfo.value)


@pytest.mark.unit
async def test_read_only_control_port_write_refuses_with_route_scope_and_prefix() -> None:
    port = ReadOnlyControlPort(
        _RecordingPort(),
        scope="route",
        prefix="2bma:shutter:",
    )
    with pytest.raises(ControlWritesDisabledError) as excinfo:
        await port.write("2bma:shutter:open", 1)
    assert excinfo.value.scope == "route"
    assert excinfo.value.prefix == "2bma:shutter:"
    assert "2bma:shutter:" in str(excinfo.value)


@pytest.mark.unit
async def test_read_only_control_port_never_reaches_inner_adapter_on_write() -> None:
    """The refusal is settled before any IO; nothing reached the substrate."""
    inner = _RecordingPort()
    port = ReadOnlyControlPort(inner, scope="deployment")
    with pytest.raises(ControlWritesDisabledError):
        await port.write("2bma:rot:val", 90.0)
    assert inner.writes == []


@pytest.mark.unit
async def test_read_only_control_port_write_refuses_regardless_of_kwargs() -> None:
    """No argument combination talks the guard into a write."""
    inner = _RecordingPort()
    port = ReadOnlyControlPort(inner, scope="deployment")
    with pytest.raises(ControlWritesDisabledError):
        await port.write("2bma:rot:val", 90.0, wait=False, timeout_s=0.0)
    assert inner.writes == []


@pytest.mark.unit
async def test_read_only_control_port_read_reaches_inner_adapter() -> None:
    inner = _RecordingPort()
    inner.seed("2bma:rot:val")
    port = ReadOnlyControlPort(inner, scope="deployment")
    reading = await port.read("2bma:rot:val")
    assert inner.reads == ["2bma:rot:val"]
    assert reading.value == 45.0


@pytest.mark.unit
async def test_read_only_control_port_subscribe_reaches_inner_adapter() -> None:
    """Observe-only includes streaming, not just point reads."""
    inner = _RecordingPort()
    inner.seed("2bma:rot:val")
    port = ReadOnlyControlPort(inner, scope="deployment")
    iterator = port.subscribe("2bma:rot:val")
    inner.seed("2bma:rot:val", 2.0)  # the stream yields on CHANGE
    got = await anext(iterator)
    assert inner.subscribes == ["2bma:rot:val"]
    assert got.value == 2.0
    await iterator.aclose()  # type: ignore[attr-defined]  # InMemoryControlPort returns AsyncGenerator


@pytest.mark.unit
async def test_read_only_control_port_aclose_delegates_to_inner() -> None:
    """Load-bearing: the registry skips adapters lacking aclose."""
    inner = _RecordingPort()
    port = ReadOnlyControlPort(inner, scope="deployment")
    await port.aclose()
    assert inner.closed is True


@pytest.mark.unit
async def test_read_only_control_port_aclose_tolerates_inner_without_aclose() -> None:
    port = ReadOnlyControlPort(_NoCloseCarrier(), scope="deployment")
    await port.aclose()  # must not raise


@pytest.mark.unit
def test_read_only_control_port_satisfies_control_port_protocol() -> None:
    port = ReadOnlyControlPort(InMemoryControlPort(), scope="deployment")
    assert isinstance(port, ControlPort)


class _RecordingSubstratePort:
    """Typed inner adapter recording what reached it, for the substrate guard.

    Mirrors `_RecordingPort` on the typed `ControlAddress` surface that #568's
    real substrate adapters implement.
    """

    def __init__(self) -> None:
        self.writes: list[tuple[ControlAddress, Any]] = []
        self.reads: list[ControlAddress] = []
        self.subscribes: list[ControlAddress] = []
        self.closed = False
        self._reading = Measurement(
            value=45.0,
            kind="Scalar",
            quality="Good",
            produced_at=datetime(2026, 7, 16, tzinfo=UTC),
        )

    async def read(self, address: ControlAddress) -> Measurement:
        self.reads.append(address)
        return self._reading

    async def write(
        self,
        address: ControlAddress,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        self.writes.append((address, value))

    def subscribe(self, address: ControlAddress) -> AsyncIterator[Measurement]:
        self.subscribes.append(address)
        return _one_measurement(self._reading)

    async def aclose(self) -> None:
        self.closed = True


class _NoCloseSubstrateCarrier:
    """Typed inner adapter with no aclose, mirroring a bare substrate double."""

    async def read(self, address: ControlAddress) -> Measurement:
        raise AssertionError("unused")

    async def write(
        self,
        address: ControlAddress,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        raise AssertionError("guard must refuse before reaching the inner adapter")

    def subscribe(self, address: ControlAddress) -> AsyncIterator[Measurement]:
        raise AssertionError("unused")


async def _one_measurement(measurement: Measurement) -> AsyncIterator[Measurement]:
    yield measurement


@pytest.mark.unit
async def test_read_only_substrate_port_write_refuses_carrying_str_address() -> None:
    """The typed guard refuses too, and str(address) names the operator's address."""
    port = ReadOnlySubstratePort(
        _RecordingSubstratePort(),
        scope="route",
        prefix="2bma:shutter:",
    )
    with pytest.raises(ControlWritesDisabledError) as excinfo:
        await port.write(InMemoryAddress("2bma:shutter:open"), 1)
    assert excinfo.value.address == "2bma:shutter:open"
    assert excinfo.value.scope == "route"
    assert excinfo.value.prefix == "2bma:shutter:"


@pytest.mark.unit
async def test_read_only_substrate_port_never_reaches_inner_on_write() -> None:
    inner = _RecordingSubstratePort()
    port = ReadOnlySubstratePort(inner, scope="deployment")
    with pytest.raises(ControlWritesDisabledError):
        await port.write(InMemoryAddress("2bma:rot:val"), 90.0)
    assert inner.writes == []


@pytest.mark.unit
async def test_read_only_substrate_port_read_reaches_inner_adapter() -> None:
    inner = _RecordingSubstratePort()
    port = ReadOnlySubstratePort(inner, scope="deployment")
    address = InMemoryAddress("2bma:rot:val")
    reading = await port.read(address)
    assert inner.reads == [address]
    assert reading.value == 45.0


@pytest.mark.unit
async def test_read_only_substrate_port_subscribe_reaches_inner_adapter() -> None:
    inner = _RecordingSubstratePort()
    port = ReadOnlySubstratePort(inner, scope="deployment")
    address = InMemoryAddress("2bma:rot:val")
    iterator = port.subscribe(address)
    got = await anext(iterator)
    assert inner.subscribes == [address]
    assert got.value == 45.0


@pytest.mark.unit
async def test_read_only_substrate_port_aclose_delegates_to_inner() -> None:
    """Load-bearing: the registry skips adapters lacking aclose."""
    inner = _RecordingSubstratePort()
    port = ReadOnlySubstratePort(inner, scope="deployment")
    await port.aclose()
    assert inner.closed is True


@pytest.mark.unit
async def test_read_only_substrate_port_aclose_tolerates_inner_without_aclose() -> None:
    port = ReadOnlySubstratePort(_NoCloseSubstrateCarrier(), scope="deployment")
    await port.aclose()  # must not raise
