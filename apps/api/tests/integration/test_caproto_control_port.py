"""Integration tests: `CaprotoControlPort` against a shared softIOC subprocess.

Originally the caproto-client ran against an in-process caproto IOC.
The test surface later moved to an `epicscorelibs.ioc` subprocess
(see [[project_control_port_test_isolation_research]]):
that change is the corpus-unanimous pattern across Diamond aioca,
ophyd-async, fastcs, and caproto's own client tests. The same
fixture serves `EpicsCaControlPort` tests; one surface for all
ControlPort adapter integration tests.

The `softioc` fixture (`tests/integration/conftest.py`,
module-scoped) yields the PV prefix. The session-scoped
`_pin_epics_env` autouse fixture has already locked EPICS env vars
to the per-worker loopback port. The function-scoped
`_purge_aioca_caches` autouse runs after each test (no-op when the
test doesn't touch aioca : caproto has its own per-Context
isolation).

Test pattern: write-then-read for any value assertion (state
persists across tests within the module since the softIOC is
shared). Quality + nonexistent-PV paths don't mutate state and
stay order-independent.

## Coverage

  - Protocol conformance via `isinstance`
  - Every `MeasurementKind` branch (Scalar / Array / Categorical)
  - `Quality=Bad` ACL path via `bad_quality_value`
    (`ao` with HIHI threshold tripped on the EPICS .db)
  - caput-callback round-trip on scalar + long
  - subscribe initial-value + post-write fan-out
  - subscribe consumer-cancellation cleanup
  - 3 nonexistent-PV `ControlNotConnectedError` paths
  - aclose idempotency

Out of scope here:

  - `ControlTimeoutError` on the read path : no softIOC-native slow-
    getter equivalent; covered at unit tier with mocked client per
    [[project_control_port_test_isolation_research]] watch item 4.
  - `Image` / `Tabular` `MeasurementKind` : CA does not natively carry
    NTNDArray; lands with `EpicsPvaControlPort`.
  - `Uncertain` quality : no convenient MINOR-alarm trigger on this
    softIOC PV menu without a calc record; defer to the PVA adapter.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio

import pytest

from cora.operation.adapters.caproto_control_port import CaprotoControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlPort,
    Measurement,
)


@pytest.mark.integration
def test_caproto_control_port_satisfies_control_port_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol."""
    assert isinstance(CaprotoControlPort(), ControlPort)


@pytest.mark.integration
async def test_read_double_scalar_returns_reading_with_good_quality(
    softioc: str,
) -> None:
    """DBR_DOUBLE scalar lands as Measurement(kind='Scalar', quality='Good', value=float)."""
    port = CaprotoControlPort()
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
    port = CaprotoControlPort()
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
    port = CaprotoControlPort()
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
    port = CaprotoControlPort()
    try:
        await port.write(f"{softioc}waveform", (1.0, 2.0, 3.0, 4.0), wait=True)
        reading = await port.read(f"{softioc}waveform")
        assert reading.kind == "Array"
        assert isinstance(reading.value, tuple)
        assert reading.value == (1.0, 2.0, 3.0, 4.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_enum_returns_categorical_kind(softioc: str) -> None:
    """DBR_ENUM lands as Measurement(kind='Categorical').

    Parity carve-out vs `EpicsCaControlPort`: aioca's `caput` accepts
    the string label and translates internally; caproto's `caput`
    requires the integer index. To avoid forcing one shape into the
    other, this test asserts kind only. The aioca twin asserts both
    kind + label (since aioca handles both directions natively).
    """
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{softioc}enum_value")
        assert reading.kind == "Categorical"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_major_alarm_pv_returns_bad_quality(softioc: str) -> None:
    """MAJOR_ALARM severity (HIHI threshold tripped) translates to Quality='Bad'.

    Pins the full Measurement shape for a non-Good reading: value + kind +
    quality + the cross-adapter `alarm_status=<int>` quality_detail
    format + tz-aware UTC produced_at. Mirrors the same set of
    assertions on EpicsCa + EpicsPva so the three adapters present
    the same Measurement shape end-to-end for the same softIOC PV.
    """
    port = CaprotoControlPort()
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
    port = CaprotoControlPort()
    try:
        await port.write(f"{softioc}double_value", 4.2, wait=True)
        reading = await port.read(f"{softioc}double_value")
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_long_then_read_observes_new_value(softioc: str) -> None:
    """DBR_LONG write round-trip pin: integer survives caput-callback + read."""
    port = CaprotoControlPort()
    try:
        await port.write(f"{softioc}long_value", 99, wait=True)
        reading = await port.read(f"{softioc}long_value")
        assert reading.value == 99
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_value_then_writes(softioc: str) -> None:
    """Subscribe gets the current value first, then each write fans out as a Measurement."""
    port = CaprotoControlPort()
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
    """Cancellation mid-`anext` runs the generator's `finally` and unregisters."""
    port = CaprotoControlPort()
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
    """A PV no IOC serves never connects; short timeout becomes ControlNotConnectedError."""
    port = CaprotoControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError) as exc_info:
            await port.read(f"{softioc}nonexistent")
        assert exc_info.value.address == f"{softioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Write path mirrors read path: never-connect surfaces as ControlNotConnectedError."""
    port = CaprotoControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError):
            await port.write(f"{softioc}nonexistent", 1.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Subscribe path mirrors read path: never-connect surfaces as ControlNotConnectedError.

    Setup is lazy per the Protocol's subscribe contract: `port.subscribe()`
    returns the iterator synchronously, and PV-resolve + `wait_for_connection`
    fire on the first `anext`. So the exception emerges from `anext`, not
    from `subscribe()` itself.
    """
    port = CaprotoControlPort(default_timeout_s=0.3)
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
    """Second aclose() call is a no-op."""
    port = CaprotoControlPort()
    await port.read(f"{softioc}double_value")
    await port.aclose()
    await port.aclose()
    assert port._context is None  # pyright: ignore[reportPrivateUsage]
