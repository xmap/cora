"""Integration tests: `TangoControlPort` (PyTango) against a real in-process device.

Production Tango adapter of the control-port arc per
[[project_control_port_design]] +
[[project_control_port_generalization_research]]. Real PyTango client
(pytango / cppTango over omniORB) talking to a real Tango device server
that `tango.test_context.DeviceTestContext` runs inside the test process.

The Tango twin of the EPICS `softioc` fixture, and a cheaper one: there is
no Tango database and no subprocess. The context mints a no-database TRL
(`tango://127.0.0.1:<free-port>/test/nodb/controlportprobe#dbase=no`) on a
loopback port and serves it from a thread, so nothing is faked between the
adapter and the Tango core.

The module-scoped `tango_device` fixture stays local rather than moving to
`tests/integration/conftest.py`: `softioc` is shared because two modules
need it, and this is the only Tango module. Move it when a second arrives.

Test pattern: write-then-read for any value assertion, since device state
persists across tests within the module. Quality and failure paths do not
mutate state and stay order-independent.

## Two Tango-specific constraints the EPICS pattern does not carry

  - Session-scoped event loop is mandatory. PyTango's asyncio green mode
    caches one process-global executor bound to the first running loop it
    ever sees. Under the repo's default function-scoped loop, only the
    first async Tango test per worker passes and the rest die with
    `RuntimeError: Event loop is closed`. Module scope is not enough
    either once a second Tango module exists, so this pins `session`
    locally rather than moving the global default.
  - One `DeviceTestContext` per process (omniORB runs a single ORB, and a
    second context's `stop()` raises `BAD_INV_ORDER_ORBHasShutdown`). The
    module-scoped fixture satisfies this. xdist workers are separate
    processes, so `-n 4` is unaffected.

## Coverage

  - Protocol conformance via `isinstance` (no device)
  - Every `MeasurementKind` branch (Scalar / Array / Image / Categorical)
  - `Quality=Uncertain` via a device-declared ATTR_WARNING attribute
  - `Quality=Bad` with no value via a device-declared ATTR_INVALID
    spectrum (the shape the Tango core forces on an invalid read)
  - Write round-trip on a scalar, and the value-coercion failure path
  - `ControlAccessDeniedError` via API_AttrNotWritable on a read-only
    attribute
  - DevEnum label resolution off the attribute config, and DevState off
    the value's own name
  - subscribe initial synchronised event + post-write fan-out
  - aclose idempotency

Out of scope:

  - Timeout paths (the adapter never calls `set_timeout_millis`, so
    PyTango's 3000 ms client default caps every call): lands with that
    fix, since asserting it here would pin a wall-clock defect.
  - Read failures surfacing as `ControlWriteRejectedError`: real, but the
    correct class is an open port-taxonomy question (`ControlPort` has no
    read-failure family), so this waits on that decision rather than
    asserting a class we have not chosen.
  - Event-error handling (`API_EventTimeout` is treated as terminal
    though Tango self-heals): needs ~10 s of real heartbeat per
    assertion; lands with that fix.
  - `set_access_control` authorisation refusals (`API_ReadOnlyMode`): the
    adapter matches an `API_UnauthorizedAccess` literal cppTango never
    emits; lands with that fix.
"""

# PyTango's server decorators are untyped: `@attribute` plus its `.write`
# sibling reads as a redeclaration of the same name, and the device methods
# it wraps come back partially unknown. Same posture as the EPICS
# integration modules, which suppress the same rules for aioca / p4p.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportRedeclaration=false

import asyncio
import time
from collections.abc import Iterator

import pytest

pytest.importorskip("tango", reason="TangoControlPort needs the optional 'tango' extra")

from tango import AttrQuality, AttrWriteType, DevState
from tango.server import Device, attribute
from tango.test_context import DeviceTestContext

from cora.operation.adapters.tango_control_port import TangoControlPort
from cora.operation.ports.control_address import TangoAttributeAddress
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlPort,
    ControlValueCoercionError,
    Measurement,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class ControlPortProbe(Device):
    """Device exposing one attribute per adapter branch under test."""

    _scalar = 2.5
    _shutter = 1
    _pushed = 0.0

    def init_device(self) -> None:
        super().init_device()
        self.set_change_event("pushed", True, False)

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE)
    def double_scalar(self) -> float:
        return self._scalar

    @double_scalar.write
    def double_scalar(self, value: float) -> None:
        self._scalar = value

    @attribute(dtype=(float,), max_dim_x=3)
    def spectrum(self) -> list[float]:
        return [1.0, 2.0, 3.0]

    @attribute(dtype=((int,),), max_dim_x=2, max_dim_y=2)
    def image(self) -> list[list[int]]:
        return [[1, 2], [3, 4]]

    @attribute(dtype=DevState)
    def state_attr(self) -> DevState:
        return DevState.RUNNING

    @attribute(
        dtype="DevEnum",
        enum_labels=["CLOSED", "OPEN", "FAULT"],
        access=AttrWriteType.READ_WRITE,
    )
    def shutter(self) -> int:
        return self._shutter

    @shutter.write
    def shutter(self, value: int) -> None:
        self._shutter = value

    @attribute(dtype=float)
    def warned(self) -> tuple[float, float, AttrQuality]:
        return 1.0, time.time(), AttrQuality.ATTR_WARNING

    @attribute(dtype=(float,), max_dim_x=3)
    def invalid_spectrum(self) -> tuple[list[float], float, AttrQuality]:
        return [1.0, 2.0, 3.0], time.time(), AttrQuality.ATTR_INVALID

    @attribute(dtype=float, access=AttrWriteType.READ)
    def readonly_attr(self) -> float:
        return 1.0

    @attribute(dtype=float, access=AttrWriteType.READ_WRITE)
    def pushed(self) -> float:
        return self._pushed

    @pushed.write
    def pushed(self, value: float) -> None:
        self._pushed = value
        self.push_change_event("pushed", value)


@pytest.fixture(scope="module")
def tango_device() -> Iterator[str]:
    """Real in-process Tango device server; yields its no-database TRL."""
    context = DeviceTestContext(ControlPortProbe, process=False)
    context.start()
    try:
        yield context.get_device_access()
    finally:
        context.stop()


def _addr(device: str, attribute_name: str) -> TangoAttributeAddress:
    """The typed address `ControlPortRegistry` parses out of a route match."""
    return TangoAttributeAddress(device=device, attribute=attribute_name)


@pytest.mark.integration
async def test_tango_control_port_satisfies_control_port_protocol() -> None:
    assert isinstance(TangoControlPort(), ControlPort)


@pytest.mark.integration
async def test_read_double_scalar_returns_good_scalar_measurement(
    tango_device: str,
) -> None:
    port = TangoControlPort()
    try:
        await port.write(_addr(tango_device, "double_scalar"), 2.5)
        reading = await port.read(_addr(tango_device, "double_scalar"))
        assert isinstance(reading, Measurement)
        assert reading.kind == "Scalar"
        assert reading.quality == "Good"
        assert reading.value == 2.5
        assert reading.quality_detail == ""
        assert reading.name == "double_scalar"
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_scalar_then_read_observes_written_value(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        await port.write(_addr(tango_device, "double_scalar"), 4.2)
        reading = await port.read(_addr(tango_device, "double_scalar"))
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_spectrum_returns_array_of_python_floats(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        reading = await port.read(_addr(tango_device, "spectrum"))
        assert reading.kind == "Array"
        assert reading.value == (1.0, 2.0, 3.0)
        assert all(type(item) is float for item in reading.value)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_image_returns_tuple_of_row_tuples(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        reading = await port.read(_addr(tango_device, "image"))
        assert reading.kind == "Image"
        assert reading.value == ((1, 2), (3, 4))
        assert all(type(cell) is int for row in reading.value for cell in row)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_devstate_returns_categorical_state_name(tango_device: str) -> None:
    """DevState really does arrive as an IntEnum, so the adapter's `.name` branch fits."""
    port = TangoControlPort()
    try:
        reading = await port.read(_addr(tango_device, "state_attr"))
        assert reading.kind == "Categorical"
        assert reading.value == "RUNNING"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_devenum_returns_categorical_label(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        await port.write(_addr(tango_device, "shutter"), 1)
        reading = await port.read(_addr(tango_device, "shutter"))
        assert reading.kind == "Categorical"
        assert reading.value == "OPEN"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_devenum_after_write_reflects_the_new_label(tango_device: str) -> None:
    """Labels are cached per address, so a later read must still track the value."""
    port = TangoControlPort()
    try:
        await port.write(_addr(tango_device, "shutter"), 2)
        reading = await port.read(_addr(tango_device, "shutter"))
        assert reading.value == "FAULT"
        await port.write(_addr(tango_device, "shutter"), 0)
        assert (await port.read(_addr(tango_device, "shutter"))).value == "CLOSED"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_warning_quality_collapses_to_uncertain(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        reading = await port.read(_addr(tango_device, "warned"))
        assert reading.quality == "Uncertain"
        assert "ATTR_WARNING" in reading.quality_detail
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_invalid_quality_array_returns_bad_reading_with_no_value(
    tango_device: str,
) -> None:
    """Tango discards the value on ATTR_INVALID but keeps data_format.

    So the kind stays `Array` with nothing to unpack. The reading carries
    that as a None value against Bad quality rather than raising, which is
    what an invalid scalar already does, and keeps the ATTR_INVALID
    breadcrumb the Conductor records against the failed step.
    """
    port = TangoControlPort()
    try:
        reading = await port.read(_addr(tango_device, "invalid_spectrum"))
        assert reading.kind == "Array"
        assert reading.value is None
        assert reading.quality == "Bad"
        assert "ATTR_INVALID" in reading.quality_detail
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_to_readonly_attribute_raises_access_denied(
    tango_device: str,
) -> None:
    port = TangoControlPort()
    try:
        with pytest.raises(ControlAccessDeniedError):
            await port.write(_addr(tango_device, "readonly_attr"), 1.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_wrong_value_type_raises_value_coercion(tango_device: str) -> None:
    port = TangoControlPort()
    try:
        with pytest.raises(ControlValueCoercionError):
            await port.write(_addr(tango_device, "double_scalar"), "not-a-number")
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_event_then_one_per_write(
    tango_device: str,
) -> None:
    port = TangoControlPort()
    address = _addr(tango_device, "pushed")
    try:
        await port.write(address, 0.0)
        iterator = port.subscribe(address)
        first = await asyncio.wait_for(anext(iterator), timeout=8.0)
        assert first.kind == "Scalar"
        assert first.quality == "Good"

        await port.write(address, 7.7)
        second = await asyncio.wait_for(anext(iterator), timeout=8.0)
        assert second.value == 7.7
        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_aclose_after_read_is_idempotent(tango_device: str) -> None:
    port = TangoControlPort()
    await port.read(_addr(tango_device, "double_scalar"))
    await port.aclose()
    await port.aclose()
