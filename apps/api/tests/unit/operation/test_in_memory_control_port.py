"""Behavioural tests for `InMemoryControlPort` + Protocol conformance.

`test_in_memory_control_port_satisfies_control_port_protocol` is the
runtime conformance check via `@runtime_checkable` `isinstance`;
pyright catches signature drift statically, isinstance catches
method-name drift at runtime. Subsequent production adapters
(Caproto / EpicsCa / EpicsPva, future Tango / OPC UA) will reuse
this pattern.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from cora.operation.adapters.in_memory_control_port import InMemoryControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlPort,
    Measurement,
    MeasurementKind,
    Quality,
)

_FIXED_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)


def _port() -> InMemoryControlPort:
    return InMemoryControlPort(now=lambda: _FIXED_NOW)


def _reading(value: Any, kind: MeasurementKind = "Scalar") -> Measurement:
    return Measurement(value=value, kind=kind, quality="Good", produced_at=_FIXED_NOW)


@pytest.mark.unit
def test_in_memory_control_port_satisfies_control_port_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol.

    Catches method-name drift at runtime (pyright catches signature drift
    statically). If `InMemoryControlPort` renames `read` to `fetch`, this
    fails immediately.
    """
    port = _port()
    assert isinstance(port, ControlPort)


@pytest.mark.unit
async def test_read_on_never_connected_address_raises_not_connected() -> None:
    port = _port()
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read("2bm:rot:rbv")
    assert exc_info.value.address == "2bm:rot:rbv"


@pytest.mark.unit
async def test_read_after_simulate_disconnect_raises_not_connected() -> None:
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(1.5))
    port.simulate_disconnect("2bm:rot:rbv")
    with pytest.raises(ControlNotConnectedError):
        await port.read("2bm:rot:rbv")


@pytest.mark.unit
async def test_write_on_never_connected_address_raises_not_connected() -> None:
    port = _port()
    with pytest.raises(ControlNotConnectedError):
        await port.write("2bm:rot:val", 3.14)


@pytest.mark.unit
async def test_set_reading_makes_address_observable_via_read() -> None:
    port = _port()
    expected = _reading(2.5)
    port.set_reading("2bm:rot:rbv", expected)
    actual = await port.read("2bm:rot:rbv")
    assert actual == expected


@pytest.mark.unit
async def test_write_then_read_round_trips_scalar() -> None:
    port = _port()
    port.simulate_connect("2bm:rot:val")
    await port.write("2bm:rot:val", 4.2)
    got = await port.read("2bm:rot:val")
    assert got.kind == "Scalar"
    assert got.value == 4.2
    assert got.quality == "Good"
    assert got.produced_at == _FIXED_NOW


@pytest.mark.unit
async def test_write_then_read_round_trips_array_as_tuple() -> None:
    port = _port()
    port.simulate_connect("2bm:cam:image")
    await port.write("2bm:cam:image", (1, 2, 3, 4))
    got = await port.read("2bm:cam:image")
    assert got.kind == "Array"
    assert got.value == (1, 2, 3, 4)


@pytest.mark.unit
async def test_write_ignores_wait_and_timeout_kwargs() -> None:
    """In-memory has no substrate confirmation; the kwargs are accepted but inert."""
    port = _port()
    port.simulate_connect("2bm:rot:val")
    await port.write("2bm:rot:val", 1.0, wait=False, timeout_s=0.001)
    assert (await port.read("2bm:rot:val")).value == 1.0


@pytest.mark.unit
async def test_subscribe_yields_values_pushed_after_subscription() -> None:
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    iterator = port.subscribe("2bm:rot:rbv")
    port.set_reading("2bm:rot:rbv", _reading(1.0))
    port.set_reading("2bm:rot:rbv", _reading(2.0))

    received = [(await anext(iterator)).value, (await anext(iterator)).value]
    assert received == [1.0, 2.0]
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_raises_not_connected_on_simulated_disconnect() -> None:
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    iterator = port.subscribe("2bm:rot:rbv")
    port.simulate_disconnect("2bm:rot:rbv")
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await anext(iterator)
    assert exc_info.value.address == "2bm:rot:rbv"


@pytest.mark.unit
async def test_subscribe_on_never_connected_address_raises_not_connected() -> None:
    """`subscribe()` returns the iterator synchronously; the connect-state
    check fires on first `anext` per the Protocol's lazy-setup contract.
    """
    port = _port()
    iterator = port.subscribe("2bm:rot:rbv")
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await anext(iterator)
    assert exc_info.value.address == "2bm:rot:rbv"


@pytest.mark.unit
async def test_subscribe_isolated_between_addresses() -> None:
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    port.set_reading("2bm:cam:frame", _reading(0.0))
    rot_iter = port.subscribe("2bm:rot:rbv")
    port.set_reading("2bm:cam:frame", _reading(99.0))
    port.set_reading("2bm:rot:rbv", _reading(1.0))
    got = await anext(rot_iter)
    assert got.value == 1.0
    await rot_iter.aclose()


@pytest.mark.unit
async def test_subscribe_fans_out_to_multiple_subscribers() -> None:
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    iter_a = port.subscribe("2bm:rot:rbv")
    iter_b = port.subscribe("2bm:rot:rbv")
    port.set_reading("2bm:rot:rbv", _reading(7.0))
    assert (await anext(iter_a)).value == 7.0
    assert (await anext(iter_b)).value == 7.0
    await iter_a.aclose()
    await iter_b.aclose()


@pytest.mark.unit
async def test_subscribe_yields_written_values_to_active_subscribers() -> None:
    port = _port()
    port.simulate_connect("2bm:rot:val")
    iterator = port.subscribe("2bm:rot:val")
    await port.write("2bm:rot:val", 9.5)
    got = await anext(iterator)
    assert got.value == 9.5
    assert got.kind == "Scalar"
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_cleanup_removes_queue_after_iteration_and_close() -> None:
    """Closing a consumed iterator drops its queue from the subscriber list.

    Async generators run their `finally` block only after the generator has
    been started; this test reflects realistic usage (subscribe, consume,
    close) where the cleanup pathway actually runs.
    """
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    iterator = port.subscribe("2bm:rot:rbv")
    assert len(port._subscribers["2bm:rot:rbv"]) == 1  # pyright: ignore[reportPrivateUsage]
    port.set_reading("2bm:rot:rbv", _reading(1.0))
    await anext(iterator)
    await iterator.aclose()
    assert port._subscribers["2bm:rot:rbv"] == []  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_consumer_cancellation_removes_subscriber_queue() -> None:
    """Cancellation mid-`anext` runs the generator's `finally` and unregisters.

    Pins the cancellation-safety invariant the production adapters
    must preserve.
    """
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(0.0))
    iterator = port.subscribe("2bm:rot:rbv")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(anext(iterator), timeout=0.05)
    assert port._subscribers["2bm:rot:rbv"] == []  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_simulate_disconnect_drops_cached_value() -> None:
    """Reconnect after disconnect must observe post-disconnect value, not pre.

    Mirrors real CA/PVA/Tango/OPC UA semantics: disconnect invalidates
    the cached value; a post-reconnect read returns the newly published
    value (1.5 from before disconnect must NOT leak through).
    """
    port = _port()
    port.set_reading("2bm:rot:rbv", _reading(1.5))
    port.simulate_disconnect("2bm:rot:rbv")
    port.set_reading("2bm:rot:rbv", _reading(2.5))
    got = await port.read("2bm:rot:rbv")
    assert got.value == 2.5


@pytest.mark.unit
async def test_write_default_now_yields_utc_aware_produced_at() -> None:
    """Default `now=None` path produces a tz-aware UTC datetime.

    Pins the contract production adapters inherit; tz-naive `produced_at`
    would silently break downstream PROV-O time fields.
    """
    port = InMemoryControlPort()
    port.simulate_connect("2bm:rot:val")
    await port.write("2bm:rot:val", 1.0)
    got = await port.read("2bm:rot:val")
    assert got.produced_at.tzinfo is UTC


@pytest.mark.unit
@pytest.mark.parametrize("kind", get_args(MeasurementKind))
def test_reading_accepts_every_reading_kind_literal(kind: str) -> None:
    """Pins the closed `MeasurementKind` set; an accidental narrowing fails fast."""
    if kind == "Array":
        value: Any = (1, 2)
    elif kind == "Categorical":
        value = "label"
    elif kind == "Tabular":
        value = {"col": (1, 2)}
    elif kind == "Image":
        value = ((1, 2), (3, 4))
    else:
        value = 0
    reading = Measurement(
        value=value,
        kind=kind,  # type: ignore[arg-type]
        quality="Good",
        produced_at=_FIXED_NOW,
    )
    assert reading.kind == kind


@pytest.mark.unit
@pytest.mark.parametrize("quality", get_args(Quality))
def test_reading_accepts_every_quality_literal(quality: str) -> None:
    """Pins the closed `Quality` set (`Good | Uncertain | Bad`) against
    accidental narrowing; matches OPC UA spec verbatim + NAMUR alignment.
    """
    reading = Measurement(
        value=1.0,
        kind="Scalar",
        quality=quality,  # type: ignore[arg-type]
        produced_at=_FIXED_NOW,
    )
    assert reading.quality == quality


@pytest.mark.unit
async def test_image_reading_round_trips_through_port() -> None:
    """`Image` kind survives set_reading + read + subscribe end-to-end.

    The headline supersession item (new MeasurementKind) gets behavioural
    coverage, not just dataclass-literal acceptance. Production
    adapters (especially EpicsPvaControlPort for NTNDArray and a
    future TangoControlPort for IMAGE attributes) must preserve this
    round-trip.
    """
    port = _port()
    image = ((1, 2, 3), (4, 5, 6))
    port.set_reading(
        "2bm:cam:image",
        Measurement(
            value=image,
            kind="Image",
            quality="Good",
            produced_at=_FIXED_NOW,
        ),
    )
    iterator = port.subscribe("2bm:cam:image")
    got = await port.read("2bm:cam:image")
    assert got.kind == "Image"
    assert got.value == image
    next_frame = ((7, 8, 9), (10, 11, 12))
    port.set_reading(
        "2bm:cam:image",
        Measurement(
            value=next_frame,
            kind="Image",
            quality="Good",
            produced_at=_FIXED_NOW,
        ),
    )
    streamed = await anext(iterator)
    assert streamed.kind == "Image"
    assert streamed.value == next_frame
    await iterator.aclose()


@pytest.mark.unit
async def test_non_good_quality_round_trips_through_port() -> None:
    """`Bad` + `Uncertain` qualities survive set_reading + read.

    `write` hard-codes `quality="Good"`, so only `set_reading` can
    exercise the non-Good branches. Production adapters MUST surface
    substrate-reported Uncertain / Bad qualities through the same
    Measurement shape (EPICS MINOR/MAJOR severity, Tango WARNING/CHANGING/
    ALARM, OPC UA Uncertain*/Bad* StatusCode top-bits).
    """
    port = _port()
    port.set_reading(
        "2bm:rot:rbv",
        Measurement(
            value=0.0,
            kind="Scalar",
            quality="Bad",
            produced_at=_FIXED_NOW,
            quality_detail="BadCommunicationError",
        ),
    )
    got = await port.read("2bm:rot:rbv")
    assert got.quality == "Bad"
    assert got.quality_detail == "BadCommunicationError"

    port.set_reading(
        "2bm:rot:rbv",
        Measurement(
            value=0.5,
            kind="Scalar",
            quality="Uncertain",
            produced_at=_FIXED_NOW,
            quality_detail="UncertainSensorCalibration",
        ),
    )
    got = await port.read("2bm:rot:rbv")
    assert got.quality == "Uncertain"
    assert got.quality_detail == "UncertainSensorCalibration"


@pytest.mark.unit
def test_reading_carries_adapter_specific_quality_detail() -> None:
    """`quality_detail` is the forensic breadcrumb for substrate sub-codes.

    OPC UA's ~240 named codes (`BadCommunicationError`,
    `UncertainDataSubNormal`, ...), EPICS `alarm_status`, and Tango
    string detail all land here without expanding the closed `Quality`
    enum.
    """
    reading = Measurement(
        value=0.0,
        kind="Scalar",
        quality="Bad",
        produced_at=_FIXED_NOW,
        quality_detail="BadCommunicationError",
    )
    assert reading.quality_detail == "BadCommunicationError"
