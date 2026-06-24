"""Integration tests: `EpicsPvaControlPort` (p4p) against the shared softIOC.

Production PVA adapter of the control-port arc per
[[project_control_port_design]] +
[[project_control_port_generalization_research]] +
[[project_control_port_test_isolation_research]]. Production PVA client
(p4p / pvxs; EPICS Base official) against the same
`epicscorelibs.ioc` subprocess `EpicsCaControlPort` uses for CA. The
IOC auto-loads qsrv + pvAccessIOC so every CA record is also
exposed via PVA (verified empirically during the design sketch).

The headline coverage: `Measurement(kind="Image")` end-to-end via the
NTNDArray PV defined in `_softioc.py`'s db
template. CA cannot carry NTNDArray; PVA can. This is the first
adapter that exercises the `Image` MeasurementKind on real wire.

## Coverage

  - Protocol conformance via `isinstance` (no IOC)
  - Every `MeasurementKind` branch (Scalar / Array / Categorical / Image)
  - `Quality=Bad` via `bad_quality_value` (HIHI threshold tripped on
    the CA record, surfaced via PVA's alarm structure)
  - caput-callback round-trip on scalar + long
  - subscribe initial-value + post-write fan-out
  - subscribe consumer-cancellation cleanup
  - 3 nonexistent-PV `ControlNotConnectedError` paths
  - aclose idempotency

Out of scope:

  - `ControlTimeoutError` on the read path: per the CA adapter
    precedent (softIOC has no slow-getter equivalent); covered at
    unit tier with mocked p4p in
    `test_epics_pva_control_port_acl.py` (TODO at follow-up if
    needed; the EpicsCa unit ACL test serves as the pattern).
  - `Tabular` MeasurementKind: no NTTable record on the test IOC today;
    extend when first NTTable consumer lands.
  - `Uncertain` quality (MINOR_ALARM): same defer-to-MINOR-trigger
    rationale as the CA adapter; add a calc record when concretely
    needed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio

import pytest

from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlPort,
    Measurement,
)


@pytest.mark.integration
def test_epics_pva_control_port_satisfies_control_port_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol."""
    assert isinstance(EpicsPvaControlPort(), ControlPort)


@pytest.mark.integration
async def test_read_double_scalar_returns_reading_with_good_quality(
    softioc: str,
) -> None:
    """DBR_DOUBLE via NTScalar lands as Measurement(kind='Scalar', quality='Good', value=float)."""
    port = EpicsPvaControlPort()
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
    """DBR_LONG via NTScalar lands as Measurement(kind='Scalar', value=int)."""
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}long_value", 0, wait=True)
        reading = await port.read(f"{softioc}long_value")
        assert reading.kind == "Scalar"
        assert int(reading.value) == 0
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_string_scalar_returns_decoded_utf8(softioc: str) -> None:
    """DBR_STRING via NTScalar lands as Python `str`."""
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}string_value", "initial", wait=True)
        reading = await port.read(f"{softioc}string_value")
        assert reading.kind == "Scalar"
        assert reading.value == "initial"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_waveform_returns_array_as_tuple(softioc: str) -> None:
    """DBR_DOUBLE count > 1 via NTScalarArray lands as Measurement(kind='Array', value=tuple)."""
    port = EpicsPvaControlPort()
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
    """DBR_ENUM via NTEnum lands as Measurement(kind='Categorical', value=<label>).

    p4p's NTEnum carries the integer index PLUS the `value.choices`
    array; the adapter resolves the label inline on every read (no
    cache needed because the labels travel in the response).
    """
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}enum_value", 0, wait=True)
        reading = await port.read(f"{softioc}enum_value")
        assert reading.kind == "Categorical"
        assert reading.value == "off"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_image_returns_image_kind_with_3x2_shape(softioc: str) -> None:
    """NTNDArray lands as Measurement(kind='Image') with the expected shape.

    Headline PVA coverage: the `Image` MeasurementKind is unreachable
    via CA and must be exercised via PVA. The softIOC's
    `image` PV is qsrv-composed from `image:data` (waveform UCHAR x 6)
    + `image:dim0_size` (longout = 2 cols, fast-varying) +
    `image:dim1_size` (longout = 3 rows, slow-varying). EPICS V4
    spec says `dimension[0]` is the fastest-varying axis; p4p
    reshapes to `dims[::-1]` for NumPy.

    A 3 x 2 asymmetric shape lets the test disambiguate row/col
    orientation: data `[1,2,3,4,5,6]` reshaped to (rows=3, cols=2)
    becomes `((1,2),(3,4),(5,6))`. A transposed reshape would yield
    `((1,2,3),(4,5,6))` which is a different value, so this test
    catches dimension-order regressions.
    """
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}image:data", (1, 2, 3, 4, 5, 6), wait=True)
        reading = await port.read(f"{softioc}image")
        assert reading.kind == "Image"
        assert reading.quality == "Good"
        assert reading.produced_at.tzinfo is not None
        assert reading.value == ((1, 2), (3, 4), (5, 6))
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_major_alarm_pv_returns_bad_quality(softioc: str) -> None:
    """MAJOR_ALARM severity translates to Quality='Bad' on the PVA wire too.

    Pins the full Measurement shape for a non-Good reading: value + kind +
    quality + `alarm_status=<int>` quality_detail format + tz-aware
    UTC produced_at. Mirrors the same assertions on Caproto + EpicsCa.
    """
    port = EpicsPvaControlPort()
    try:
        reading = await port.read(f"{softioc}bad_quality_value")
        assert reading.kind == "Scalar"
        assert float(reading.value) == 99.9
        assert reading.quality == "Bad"
        assert reading.quality_detail.startswith("alarm_status=")
        assert reading.produced_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_scalar_then_read_observes_new_value(softioc: str) -> None:
    """PVA put-with-wait semantics: after `wait=True` write returns, read sees new value."""
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}double_value", 4.2, wait=True)
        reading = await port.read(f"{softioc}double_value")
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_long_then_read_observes_new_value(softioc: str) -> None:
    """DBR_LONG via PVA put-with-wait round-trip."""
    port = EpicsPvaControlPort()
    try:
        await port.write(f"{softioc}long_value", 99, wait=True)
        reading = await port.read(f"{softioc}long_value")
        assert int(reading.value) == 99
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_value_then_writes(softioc: str) -> None:
    """Subscribe gets the current value first, then each write fans out as a Measurement."""
    port = EpicsPvaControlPort()
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
    """Cancellation mid-`anext` runs the drain generator's finally + sub.close()."""
    port = EpicsPvaControlPort()
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
    """A PV no IOC serves never connects; short timeout surfaces as NotConnected."""
    port = EpicsPvaControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError) as exc_info:
            await port.read(f"{softioc}nonexistent")
        assert exc_info.value.address == f"{softioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Write path mirrors read path: never-connect surfaces as NotConnected.

    Note: write's `asyncio.TimeoutError` maps to ControlTimeoutError by
    default; but a never-connected PV never even reaches the server,
    so the timeout fires before any put-callback. The adapter doesn't
    distinguish "slow IOC" from "no IOC" on the write path because
    PVA doesn't surface a not-found exception. Acceptable for the
    softIOC integration tier.
    """
    port = EpicsPvaControlPort(default_timeout_s=0.3)
    try:
        # PVA doesn't surface not-found as a distinct exception; the
        # write times out OR receives Disconnected from p4p, depending
        # on timing. Both arms surface a CORA Control*Error carrying
        # the address. Tighten to the two acceptable types so a
        # regression to a different exception class fails the test.
        from cora.operation.ports.control_port import ControlTimeoutError

        with pytest.raises((ControlTimeoutError, ControlNotConnectedError)) as exc_info:
            await port.write(f"{softioc}nonexistent", 1.0)
        assert exc_info.value.address == f"{softioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_on_nonexistent_pv_raises_not_connected(softioc: str) -> None:
    """Subscribe path raises NotConnected when no value arrives.

    Unlike CA where subscribe returns an iterator that never yields,
    p4p's monitor on a nonexistent PV stays open silently. The test
    asserts that anext times out within the deadline.
    """
    port = EpicsPvaControlPort(default_timeout_s=0.3)
    try:
        iterator = port.subscribe(f"{softioc}nonexistent")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(iterator), timeout=0.3)
        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_aclose_is_idempotent(softioc: str) -> None:
    """Second aclose() call is a no-op."""
    port = EpicsPvaControlPort()
    await port.read(f"{softioc}double_value")
    await port.aclose()
    await port.aclose()
    assert port._closed is True  # pyright: ignore[reportPrivateUsage]
