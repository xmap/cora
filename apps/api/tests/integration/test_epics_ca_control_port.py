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
  - DBR_CHAR waveform: undeclared (Array-of-bytes), declared via
    `text_addresses` (decoded Scalar str, both read + subscribe),
    NUL-padding trim, and the inert case (declaring a non-char PV)
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
from cora.operation.ports.control_address import EpicsPvAddress
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
        await port.write(EpicsPvAddress(f"{softioc}double_value"), 0.0, wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}double_value"))
        assert isinstance(reading, Measurement)
        assert reading.kind == "Scalar"
        assert reading.quality == "Good"
        assert reading.value == 0.0
        assert reading.produced_at is not None
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_long_scalar_returns_int_value(softioc: str) -> None:
    """DBR_LONG scalar lands as Measurement(kind='Scalar', value=int)."""
    port = EpicsCaControlPort()
    try:
        await port.write(EpicsPvAddress(f"{softioc}long_value"), 0, wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}long_value"))
        assert reading.kind == "Scalar"
        assert reading.value == 0
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_string_scalar_returns_decoded_utf8(softioc: str) -> None:
    """DBR_STRING scalar lands decoded as Python `str`, not raw `bytes`."""
    port = EpicsCaControlPort()
    try:
        await port.write(EpicsPvAddress(f"{softioc}string_value"), "initial", wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}string_value"))
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
        await port.write(EpicsPvAddress(f"{softioc}waveform"), (1.0, 2.0, 3.0, 4.0), wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}waveform"))
        assert reading.kind == "Array"
        assert isinstance(reading.value, tuple)
        assert reading.value == (1.0, 2.0, 3.0, 4.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_char_waveform_without_declaration_returns_array_of_bytes(
    softioc: str,
) -> None:
    """DBR_CHAR waveform is Array-of-int by default: the ambiguous case, undeclared.

    Same shape a byte-array payload (an NTNDArray image) would take;
    this is the reading a deployment gets before it tells the adapter
    which addresses actually carry text via `text_addresses`.
    """
    port = EpicsCaControlPort()
    try:
        await port.write(
            EpicsPvAddress(f"{softioc}text_waveform"),
            tuple(b"hello"),
            wait=True,
        )
        reading = await port.read(EpicsPvAddress(f"{softioc}text_waveform"))
        assert reading.kind == "Array"
        assert reading.value == (104, 101, 108, 108, 111)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_char_waveform_declared_as_text_returns_decoded_string(
    softioc: str,
) -> None:
    """A declared `text_addresses` entry decodes the same wire reading as text.

    Models tomoscan's `ScanStatus` / `FileName` / `FullFileName`: a
    DBR_CHAR waveform an operator knows carries a NUL-terminated
    string, told to the adapter because EPICS gives it no way to tell
    that apart from a byte-array payload on its own.
    """
    pv = f"{softioc}text_waveform"
    port = EpicsCaControlPort(text_addresses={pv})
    try:
        await port.write(EpicsPvAddress(pv), tuple(b"fdt file transfer complete"), wait=True)
        reading = await port.read(EpicsPvAddress(pv))
        assert reading.kind == "Scalar"
        assert reading.value == "fdt file transfer complete"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_char_waveform_declared_as_text_trims_trailing_nul_padding(
    softioc: str,
) -> None:
    """A shorter message than NELM leaves trailing padding; decode stops at the first NUL."""
    pv = f"{softioc}text_waveform"
    port = EpicsCaControlPort(text_addresses={pv})
    try:
        padded = tuple(b"hi") + (0,) * 254
        await port.write(EpicsPvAddress(pv), padded, wait=True)
        reading = await port.read(EpicsPvAddress(pv))
        assert reading.value == "hi"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_declaring_a_non_char_address_as_text_is_inert(softioc: str) -> None:
    """`text_addresses` naming a non-DBR_CHAR PV changes nothing: it cannot manufacture a type."""
    pv = f"{softioc}waveform"
    port = EpicsCaControlPort(text_addresses={pv})
    try:
        await port.write(EpicsPvAddress(pv), (1.0, 2.0, 3.0, 4.0), wait=True)
        reading = await port.read(EpicsPvAddress(pv))
        assert reading.kind == "Array"
        assert reading.value == (1.0, 2.0, 3.0, 4.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_declaring_a_length_one_char_waveform_as_text_does_not_raise(
    softioc: str,
) -> None:
    """A length-1 DBR_CHAR waveform must stay inert under `text_addresses`, not crash.

    aioca collapses `element_count == 1` to its scalar `ca_int` type,
    which is neither iterable nor has `.tolist()`. `_to_reading` gates
    `as_text` on `element_count > 1` for exactly this reason: without
    it, decoding this reading as a waveform raises `TypeError` instead
    of falling through to the ordinary (already-Scalar) path.
    """
    pv = f"{softioc}text_waveform_nelm1"
    port = EpicsCaControlPort(text_addresses={pv})
    try:
        await port.write(EpicsPvAddress(pv), (ord("Q"),), wait=True)
        reading = await port.read(EpicsPvAddress(pv))
        assert reading.kind == "Scalar"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_char_waveform_declared_as_text_yields_decoded_strings(
    softioc: str,
) -> None:
    """Subscribe honours the same declaration as read, per update."""
    pv = f"{softioc}text_waveform"
    port = EpicsCaControlPort(text_addresses={pv})
    try:
        await port.write(EpicsPvAddress(pv), tuple(b"scan started"), wait=True)
        iterator = port.subscribe(EpicsPvAddress(pv))
        first = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert first.kind == "Scalar"
        assert first.value == "scan started"

        await port.write(EpicsPvAddress(pv), tuple(b"scan complete"), wait=True)
        second = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert second.value == "scan complete"

        await iterator.aclose()
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
        await port.write(EpicsPvAddress(f"{softioc}enum_value"), "off", wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}enum_value"))
        assert reading.kind == "Categorical"
        assert reading.value == "off"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_major_alarm_pv_returns_uncertain_quality(softioc: str) -> None:
    """MAJOR_ALARM severity (HIHI threshold tripped) translates to Quality='Uncertain'.

    Pins the full Measurement shape for a non-Good reading: value + kind +
    quality + `alarm_status=<int>` quality_detail format + tz-aware
    UTC produced_at. Mirrors the same assertions on Caproto + EpicsPva.
    MAJOR is a correctly-read value reporting a serious process
    condition, so it stays believable; only INVALID is Bad.
    """
    port = EpicsCaControlPort()
    try:
        reading = await port.read(EpicsPvAddress(f"{softioc}major_alarm_value"))
        assert reading.kind == "Scalar"
        assert reading.value == 99.9
        assert reading.quality == "Uncertain"
        assert reading.quality_detail.startswith("alarm_status=")
        assert reading.produced_at is not None
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_invalid_alarm_pv_returns_bad_quality(softioc: str) -> None:
    """INVALID_ALARM severity is the one severity that reaches Quality='Bad'."""
    port = EpicsCaControlPort()
    try:
        reading = await port.read(EpicsPvAddress(f"{softioc}invalid_alarm_value"))
        assert reading.quality == "Bad"
        assert reading.quality_detail.startswith("alarm_status=")
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_unstamped_pv_reports_no_produced_at(softioc: str) -> None:
    """A record that never processed has no time, and says so rather than saying 1990.

    `unstamped_value` omits `PINI`, so EPICS `TIME` stays zero. aioca
    surfaces that as the EPICS epoch, and `fromtimestamp` used to turn
    it into 1990-01-01: a date that sorts and filters like a real
    reading. The value itself is still perfectly readable, which is
    exactly why the old behaviour was hard to spot.

    This is the live APS 2-BM condition; both PSS permit signals
    behave this way on every update.
    """
    port = EpicsCaControlPort()
    try:
        reading = await port.read(EpicsPvAddress(f"{softioc}unstamped_value"))
        assert reading.value == 7.5
        assert reading.quality == "Good"
        assert reading.produced_at is None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_scalar_then_read_observes_new_value(softioc: str) -> None:
    """caput-callback semantics: after `wait=True` write returns, read sees new value."""
    port = EpicsCaControlPort()
    try:
        await port.write(EpicsPvAddress(f"{softioc}double_value"), 4.2, wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}double_value"))
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_long_then_read_observes_new_value(softioc: str) -> None:
    """DBR_LONG write round-trip pin: integer survives caput-callback + read."""
    port = EpicsCaControlPort()
    try:
        await port.write(EpicsPvAddress(f"{softioc}long_value"), 99, wait=True)
        reading = await port.read(EpicsPvAddress(f"{softioc}long_value"))
        assert reading.value == 99
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_value_then_writes(softioc: str) -> None:
    """Subscribe gets the current value first (camonitor convention), then writes fan out."""
    port = EpicsCaControlPort()
    try:
        await port.write(EpicsPvAddress(f"{softioc}double_value"), 0.0, wait=True)
        iterator = port.subscribe(EpicsPvAddress(f"{softioc}double_value"))
        first = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert first.value == 0.0

        await port.write(EpicsPvAddress(f"{softioc}double_value"), 7.7, wait=True)
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
        iterator = port.subscribe(EpicsPvAddress(f"{softioc}double_value"))
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
            await port.read(EpicsPvAddress(f"{softioc}nonexistent"))
        assert exc_info.value.address == f"{softioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Write path mirrors read path: never-connect surfaces as ControlNotConnectedError."""
    port = EpicsCaControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError):
            await port.write(EpicsPvAddress(f"{softioc}nonexistent"), 1.0)
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
        iterator = port.subscribe(EpicsPvAddress(f"{softioc}nonexistent"))
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
    await port.read(EpicsPvAddress(f"{softioc}double_value"))
    await port.aclose()
    await port.aclose()
    assert port._closed is True  # pyright: ignore[reportPrivateUsage]
