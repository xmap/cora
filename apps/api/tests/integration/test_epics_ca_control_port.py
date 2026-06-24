"""Integration tests: `EpicsCaControlPort` (aioca) against a shared softIOC.

Production CA adapter of the control-port arc per
[[project_control_port_design]] +
[[project_control_port_generalization_research]] +
[[project_control_port_test_isolation_research]]. Production CA client
(aioca / libca via ctypes; Diamond production-uses-it) talking to the
same `epicscorelibs.ioc` subprocess as `CaprotoControlPort`'s tests.

The `softioc` fixture (`tests/integration/conftest.py`, module-scoped)
yields the PV prefix. The session-scoped `_pin_epics_env` autouse
fixture has locked EPICS env vars to the per-worker loopback port.
The function-scoped `_purge_aioca_caches` autouse fixture calls
`aioca.purge_channel_caches()` after each test so subscriptions don't
leak across tests on the shared subprocess.

Test pattern: write-then-read for any value assertion (state persists
across tests within the module since softIOC is shared). Quality +
nonexistent-PV paths don't mutate state and stay order-independent.

## Coverage

  - Protocol conformance via `isinstance` (no IOC)
  - Every `MeasurementKind` branch (Scalar / Array / Categorical)
  - `Quality=Bad` via `bad_quality_value` (HIHI threshold tripped)
  - caput-callback round-trip on scalar + long
  - subscribe initial-value + post-write fan-out
  - subscribe consumer-cancellation cleanup
  - 3 nonexistent-PV `ControlNotConnectedError` paths
  - aclose idempotency

Out of scope:

  - `ControlTimeoutError` on the read path : no softIOC-native slow-
    getter equivalent; covered at unit tier with mocked client per
    [[project_control_port_test_isolation_research]] watch item 4.
  - `Image` / `Tabular` `MeasurementKind` : CA does not natively carry
    NTNDArray; lands with `EpicsPvaControlPort`.
  - `Uncertain` quality : defer to the PVA adapter (no convenient
    MINOR trigger on this PV menu without a calc record).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio

import pytest

from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlPort,
    Measurement,
)


@pytest.mark.integration
def test_epics_ca_control_port_satisfies_control_port_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol."""
    assert isinstance(EpicsCaControlPort(), ControlPort)


@pytest.mark.integration
async def test_read_double_scalar_returns_reading_with_good_quality(
    softioc: str,
) -> None:
    """DBR_DOUBLE scalar lands as Measurement(kind='Scalar', quality='Good', value=float)."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}double_value", 0.0, wait=True)
        reading = await port.read(f"{softioc}double_value")
        assert isinstance(reading, Measurement)
        assert reading.kind == "Scalar"
        assert reading.quality == "Good"
        assert reading.value == 0.0
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_long_scalar_returns_int_value(softioc: str) -> None:
    """DBR_LONG scalar lands as Measurement(kind='Scalar', value=int)."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}long_value", 0, wait=True)
        reading = await port.read(f"{softioc}long_value")
        assert reading.kind == "Scalar"
        assert reading.value == 0
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_string_scalar_returns_decoded_utf8(softioc: str) -> None:
    """DBR_STRING scalar lands decoded as Python `str`, not raw `bytes`."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}string_value", "initial", wait=True)
        reading = await port.read(f"{softioc}string_value")
        assert reading.kind == "Scalar"
        assert reading.value == "initial"
        assert isinstance(reading.value, str)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_waveform_returns_array_as_tuple(softioc: str) -> None:
    """DBR_DOUBLE count > 1 lands as Measurement(kind='Array', value=tuple)."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}waveform", (1.0, 2.0, 3.0, 4.0), wait=True)
        reading = await port.read(f"{softioc}waveform")
        assert reading.kind == "Array"
        assert isinstance(reading.value, tuple)
        assert reading.value == (1.0, 2.0, 3.0, 4.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_enum_returns_categorical_with_label(softioc: str) -> None:
    """DBR_ENUM lands as Measurement(kind='Categorical', value=<label str>).

    aioca exposes only the integer index in FORMAT_TIME; the adapter
    pays a one-shot FORMAT_CTRL read on first access to resolve the
    `enum_strings` (`off | on | fault`) and caches them per-address.
    """
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}enum_value", "off", wait=True)
        reading = await port.read(f"{softioc}enum_value")
        assert reading.kind == "Categorical"
        assert reading.value == "off"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_major_alarm_pv_returns_bad_quality(softioc: str) -> None:
    """MAJOR_ALARM severity (HIHI threshold tripped) translates to Quality='Bad'.

    Pins the full Measurement shape for a non-Good reading: value + kind +
    quality + `alarm_status=<int>` quality_detail format + tz-aware
    UTC produced_at. Mirrors the same assertions on Caproto + EpicsPva.
    """
    port = EpicsCaControlPort()
    try:
        reading = await port.read(f"{softioc}bad_quality_value")
        assert reading.kind == "Scalar"
        assert reading.value == 99.9
        assert reading.quality == "Bad"
        assert reading.quality_detail.startswith("alarm_status=")
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_scalar_then_read_observes_new_value(softioc: str) -> None:
    """caput-callback semantics: after `wait=True` write returns, read sees new value."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}double_value", 4.2, wait=True)
        reading = await port.read(f"{softioc}double_value")
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_long_then_read_observes_new_value(softioc: str) -> None:
    """DBR_LONG write round-trip pin: integer survives caput-callback + read."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}long_value", 99, wait=True)
        reading = await port.read(f"{softioc}long_value")
        assert reading.value == 99
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_value_then_writes(softioc: str) -> None:
    """Subscribe gets the current value first (camonitor convention), then writes fan out."""
    port = EpicsCaControlPort()
    try:
        await port.write(f"{softioc}double_value", 0.0, wait=True)
        iterator = port.subscribe(f"{softioc}double_value")
        first = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert first.value == 0.0

        await port.write(f"{softioc}double_value", 7.7, wait=True)
        second = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert second.value == 7.7

        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_consumer_cancellation_runs_generator_finally(softioc: str) -> None:
    """Cancellation mid-`anext` runs the drain generator's finally + sub.close."""
    port = EpicsCaControlPort()
    try:
        iterator = port.subscribe(f"{softioc}double_value")
        await asyncio.wait_for(anext(iterator), timeout=2.0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(iterator), timeout=0.05)
        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """A PV no IOC serves never connects; cainfo precondition surfaces NotConnected."""
    port = EpicsCaControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError) as exc_info:
            await port.read(f"{softioc}nonexistent")
        assert exc_info.value.address == f"{softioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Write path mirrors read path: never-connect surfaces as ControlNotConnectedError."""
    port = EpicsCaControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError):
            await port.write(f"{softioc}nonexistent", 1.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Subscribe path mirrors read path: never-connect surfaces as ControlNotConnectedError.

    Setup is lazy per the Protocol's subscribe contract: `port.subscribe()`
    returns the iterator synchronously, and `_assert_connected` fires on
    the first `anext`. So the exception emerges from `anext`, not from
    `subscribe()` itself.
    """
    port = EpicsCaControlPort(default_timeout_s=0.3)
    try:
        iterator = port.subscribe(f"{softioc}nonexistent")
        with pytest.raises(ControlNotConnectedError) as exc_info:
            await anext(iterator)
        assert exc_info.value.address == f"{softioc}nonexistent"
        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_aclose_is_idempotent(softioc: str) -> None:
    """Second aclose() call is a no-op (matches Caproto + InMemory lifecycle)."""
    port = EpicsCaControlPort()
    await port.read(f"{softioc}double_value")
    await port.aclose()
    await port.aclose()
    assert port._closed is True  # pyright: ignore[reportPrivateUsage]
