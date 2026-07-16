"""Unit-tier ACL tests for `TangoControlPort` translation + error mapping.

Mirrors `test_epics_pva_control_port_acl.py`. These tests inject a fake
`tango` / `tango.asyncio` module into `sys.modules`, neutralise the import
probe, and pre-seed the adapter's per-device proxy cache, so every ACL branch
(kind classification, quality collapse, DevFailed reason mapping, subscribe
lifecycle) runs with no substrate and no optional extra installed. Injecting a
failure by reason is also far easier against a double than against a device.

The fake earns its place at this tier only. It is not evidence that the
adapter matches PyTango: a fake written alongside the adapter encodes the same
assumptions, so both agree even where the real library disagrees with both.
`tests/integration/test_tango_control_port.py` drives the real adapter against
a real device server and is what holds the adapter to PyTango's actual
behaviour. Keep the two in step: when a branch here asserts a shape, the
integration module is where that shape is confirmed to be real.

Coverage:

  - kind classification: SCALAR / SPECTRUM / IMAGE / DevEnum ->
    Scalar / Array / Image / Categorical
  - quality collapse: VALID -> Good; WARNING / CHANGING -> Uncertain;
    ALARM / INVALID -> Bad
  - read timeout -> ControlNotConnectedError; write timeout -> ControlTimeoutError
  - DevFailed reason mapping: not-connected, timeout, write-rejected,
    access-denied
  - write value-coercion (ValueError / TypeError) -> ControlValueCoercionError
  - subscribe: value then err-event -> NotConnected through the iterator;
    unsubscribe called on close; aclose idempotent
  - probe: require_tango raises ValueError when PyTango is absent

The adapter now takes a typed `TangoAttributeAddress`; TRL parsing and its
malformed-address guard moved to the registry boundary and are covered in
`test_control_address.py`.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import TYPE_CHECKING, Any

import pytest

from cora.operation.ports.control_address import TangoAttributeAddress
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


_ADDR = TangoAttributeAddress(device="dev", attribute="attr")
"""The typed address every test uses; `str(_ADDR)` == "dev/attr", which the
fake proxy is seeded under (`_proxies["dev"]`) and which error breadcrumbs
carry. TRL-parsing / malformed-address coverage lives in test_control_address."""


def _no_probe(_substrate: str) -> None:
    """Neutralised `require_tango`: PyTango is absent in the base test env."""


def _no_spec(_name: str) -> None:
    """Stand-in for `importlib.util.find_spec` returning None (module absent)."""
    return None


class _DevError:
    """Stand-in for a `tango.DevError`, carrying the `.reason` the ACL reads."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


class _DevFailed(Exception):  # noqa: N818
    """Stand-in for `tango.DevFailed`: args[0] is a `_DevError` with `.reason`.

    Named to mirror PyTango's own `DevFailed` (no Error suffix) so the test
    reads against the real symbol name the adapter catches.
    """


class _Enum:
    """Minimal `.name`-carrying stand-in for a Tango enum member (quality / format / type)."""

    def __init__(self, name: str) -> None:
        self.name = name


class _TimeVal:
    def __init__(self, seconds: float) -> None:
        self._seconds = seconds

    def totime(self) -> float:
        return self._seconds


class _DeviceAttribute:
    """Stand-in for `tango.DeviceAttribute` with the fields the ACL unpacks.

    ATTR_INVALID forces `value` to None whatever the caller passes, because
    the Tango core discards the value on an invalid read while keeping
    `data_format`. Coupling the two here is what stops this double from
    expressing a reading the real substrate cannot produce: an earlier
    version took value and quality as independent kwargs, so a live value
    paired with ATTR_INVALID looked reasonable, and the invalid-array cell
    (where the adapter unpacked None as a sequence) was never reachable.
    """

    def __init__(
        self,
        *,
        value: Any,
        quality: str = "ATTR_VALID",
        data_format: str = "SCALAR",
        attr_type: str = "DevDouble",
        seconds: float = 0.0,
        name: str = "attr",
    ) -> None:
        self.value = None if quality == "ATTR_INVALID" else value
        self.quality = _Enum(quality)
        self.data_format = _Enum(data_format)
        self.type = _Enum(attr_type)
        self.time = _TimeVal(seconds)
        self.name = name


class _EventData:
    """Stand-in for a Tango CHANGE_EVENT `EventData`."""

    def __init__(self, *, attr_value: Any = None, err: bool = False) -> None:
        self.attr_value = attr_value
        self.err = err
        self.errors = ()


class _FakeProxy:
    """Programmable stand-in for `tango.asyncio.DeviceProxy`.

    `read_attribute` / `write_attribute` either return / accept, or raise a
    configured exception. `subscribe_event` invokes its callback synchronously
    with the configured event sequence (mirroring the p4p `_MonitorContext`).
    """

    def __init__(
        self,
        *,
        read_result: Any = None,
        read_raises: BaseException | None = None,
        write_raises: BaseException | None = None,
        events: tuple[Any, ...] = (),
        enum_labels: tuple[str, ...] = (),
        config_raises: BaseException | None = None,
    ) -> None:
        self._read_result = read_result
        self._read_raises = read_raises
        self._write_raises = write_raises
        self._events = events
        self._enum_labels = enum_labels
        self._config_raises = config_raises
        self.unsubscribed: list[int] = []
        self.config_reads: list[str] = []

    async def read_attribute(self, _attribute: str) -> Any:
        if self._read_raises is not None:
            raise self._read_raises
        return self._read_result

    async def get_attribute_config(self, attribute: str) -> Any:
        """Enum labels live in the CONFIG, never on the read value.

        Empty labels is what a real non-enum attribute reports, including
        DevState, so that is the default here.
        """
        self.config_reads.append(attribute)
        if self._config_raises is not None:
            raise self._config_raises
        return types.SimpleNamespace(enum_labels=self._enum_labels)

    async def write_attribute(self, _attribute: str, _value: Any) -> None:
        if self._write_raises is not None:
            raise self._write_raises

    async def subscribe_event(self, _attribute: str, _event_type: Any, callback: Any) -> int:
        for event in self._events:
            callback(event)
        return 7

    async def unsubscribe_event(self, event_id: int) -> None:
        self.unsubscribed.append(event_id)


@pytest.fixture
def fake_tango(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Inject a fake `tango` / `tango.asyncio` module and neutralise the probe.

    The adapter imports `DevFailed` / `EventType` from `tango` and
    `DeviceProxy` from `tango.asyncio` lazily inside its methods; seeding
    `sys.modules` makes those imports resolve to the stand-ins here. The
    import probe is patched to a no-op so `TangoControlPort()` constructs.
    """
    tango_mod = types.ModuleType("tango")
    tango_mod.DevFailed = _DevFailed  # pyright: ignore[reportAttributeAccessIssue]
    tango_mod.EventType = types.SimpleNamespace(  # pyright: ignore[reportAttributeAccessIssue]
        CHANGE_EVENT="change"
    )
    asyncio_mod = types.ModuleType("tango.asyncio")
    asyncio_mod.DeviceProxy = _FakeProxy  # pyright: ignore[reportAttributeAccessIssue]
    tango_mod.asyncio = asyncio_mod  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, "tango", tango_mod)
    monkeypatch.setitem(sys.modules, "tango.asyncio", asyncio_mod)
    monkeypatch.setattr("cora.operation.adapters.tango_control_port.require_tango", _no_probe)
    yield


def _make_port(**proxy_kwargs: Any) -> Any:
    """Build a `TangoControlPort` with a pre-seeded fake proxy for device `dev`."""
    from cora.operation.adapters.tango_control_port import TangoControlPort

    port = TangoControlPort(default_timeout_s=0.05)
    port._proxies["dev"] = _FakeProxy(**proxy_kwargs)  # pyright: ignore[reportPrivateUsage]
    return port


@pytest.mark.unit
async def test_read_scalar_translates_to_good_scalar_measurement(fake_tango: None) -> None:
    port = _make_port(read_result=_DeviceAttribute(value=2.5))
    reading = await port.read(_ADDR)
    assert reading.kind == "Scalar"
    assert reading.value == 2.5
    assert reading.quality == "Good"
    assert reading.quality_detail == ""


@pytest.mark.unit
async def test_read_spectrum_translates_to_array_kind(fake_tango: None) -> None:
    port = _make_port(read_result=_DeviceAttribute(value=[1.0, 2.0, 3.0], data_format="SPECTRUM"))
    reading = await port.read(_ADDR)
    assert reading.kind == "Array"
    assert reading.value == (1.0, 2.0, 3.0)


@pytest.mark.unit
async def test_read_image_translates_to_image_kind(fake_tango: None) -> None:
    port = _make_port(read_result=_DeviceAttribute(value=[[1, 2], [3, 4]], data_format="IMAGE"))
    reading = await port.read(_ADDR)
    assert reading.kind == "Image"
    assert reading.value == ((1, 2), (3, 4))


@pytest.mark.unit
async def test_read_devenum_resolves_ordinal_to_label_from_config(fake_tango: None) -> None:
    """A DevEnum read carries a bare ordinal; the label comes from the config."""
    port = _make_port(
        read_result=_DeviceAttribute(value=1, attr_type="DevEnum"),
        enum_labels=("CLOSED", "OPEN", "FAULT"),
    )
    reading = await port.read(_ADDR)
    assert reading.kind == "Categorical"
    assert reading.value == "OPEN"


@pytest.mark.unit
async def test_read_devstate_uses_value_name_without_reading_config(fake_tango: None) -> None:
    """DevState arrives as a real IntEnum, so it needs no config round trip."""
    port = _make_port(read_result=_DeviceAttribute(value=_Enum("RUNNING"), attr_type="DevState"))
    reading = await port.read(_ADDR)
    assert reading.kind == "Categorical"
    assert reading.value == "RUNNING"


@pytest.mark.unit
async def test_read_devenum_falls_back_to_ordinal_when_config_unreadable(
    fake_tango: None,
) -> None:
    """A readable attribute must not fail a step because its config is not."""
    port = _make_port(
        read_result=_DeviceAttribute(value=2, attr_type="DevEnum"),
        config_raises=_DevFailed(_DevError("API_AttrNotFound")),
    )
    reading = await port.read(_ADDR)
    assert reading.value == "2"


@pytest.mark.unit
async def test_read_devenum_ordinal_outside_labels_falls_back_to_ordinal(
    fake_tango: None,
) -> None:
    port = _make_port(
        read_result=_DeviceAttribute(value=9, attr_type="DevEnum"),
        enum_labels=("CLOSED", "OPEN"),
    )
    reading = await port.read(_ADDR)
    assert reading.value == "9"


@pytest.mark.unit
async def test_read_devenum_twice_reads_config_once(fake_tango: None) -> None:
    """The label cache keeps the config round trip off the per-read path."""
    port = _make_port(
        read_result=_DeviceAttribute(value=1, attr_type="DevEnum"),
        enum_labels=("CLOSED", "OPEN"),
    )
    await port.read(_ADDR)
    await port.read(_ADDR)
    proxy = port._proxies[_ADDR.device]  # pyright: ignore[reportPrivateUsage]
    assert proxy.config_reads == [_ADDR.attribute]


@pytest.mark.unit
async def test_read_devstate_twice_reads_config_once(fake_tango: None) -> None:
    """The negative is cached too, or every DevState read pays a round trip."""
    port = _make_port(read_result=_DeviceAttribute(value=_Enum("FAULT"), attr_type="DevState"))
    await port.read(_ADDR)
    await port.read(_ADDR)
    proxy = port._proxies[_ADDR.device]  # pyright: ignore[reportPrivateUsage]
    assert len(proxy.config_reads) <= 1


@pytest.mark.unit
async def test_aclose_drops_the_enum_label_cache(fake_tango: None) -> None:
    port = _make_port(
        read_result=_DeviceAttribute(value=1, attr_type="DevEnum"),
        enum_labels=("CLOSED", "OPEN"),
    )
    await port.read(_ADDR)
    await port.aclose()
    assert port._enum_labels == {}  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("attr_quality", "expected"),
    [
        ("ATTR_VALID", "Good"),
        ("ATTR_WARNING", "Uncertain"),
        ("ATTR_CHANGING", "Uncertain"),
        ("ATTR_ALARM", "Bad"),
        ("ATTR_INVALID", "Bad"),
    ],
)
async def test_read_collapses_attr_quality(
    fake_tango: None, attr_quality: str, expected: str
) -> None:
    port = _make_port(read_result=_DeviceAttribute(value=1.0, quality=attr_quality))
    reading = await port.read(_ADDR)
    assert reading.quality == expected
    if expected != "Good":
        assert attr_quality in reading.quality_detail


@pytest.mark.unit
@pytest.mark.parametrize(
    ("data_format", "attr_type"),
    [
        ("SCALAR", "DevDouble"),
        ("SPECTRUM", "DevDouble"),
        ("IMAGE", "DevLong"),
        ("SCALAR", "DevEnum"),
    ],
)
async def test_read_invalid_quality_returns_none_value_for_every_data_format(
    fake_tango: None, data_format: str, attr_type: str
) -> None:
    """An invalid read carries no value, and says so the same way at every kind.

    The kind still comes from `data_format` (Tango keeps it on an invalid
    read), so this pins that an invalid SPECTRUM stays `Array` while its
    value is None, rather than being unpacked as a sequence.
    """
    port = _make_port(
        read_result=_DeviceAttribute(
            value=1.0, quality="ATTR_INVALID", data_format=data_format, attr_type=attr_type
        )
    )
    reading = await port.read(_ADDR)
    assert reading.value is None
    assert reading.quality == "Bad"
    assert "ATTR_INVALID" in reading.quality_detail


@pytest.mark.unit
async def test_read_timeout_translates_to_not_connected(fake_tango: None) -> None:
    """A `wait_for` timeout on read maps to NotConnected (slow == absent at this tier)."""
    port = _make_port(read_raises=TimeoutError())
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read(_ADDR)
    assert exc_info.value.address == "dev/attr"


@pytest.mark.unit
async def test_read_dev_failed_cant_connect_translates_to_not_connected(
    fake_tango: None,
) -> None:
    port = _make_port(read_raises=_DevFailed(_DevError("API_CantConnectToDevice")))
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read(_ADDR)
    assert exc_info.value.address == "dev/attr"


@pytest.mark.unit
async def test_write_timeout_translates_to_control_timeout_error(fake_tango: None) -> None:
    port = _make_port(write_raises=TimeoutError())
    with pytest.raises(ControlTimeoutError) as exc_info:
        await port.write(_ADDR, 1.0, timeout_s=0.05)
    assert exc_info.value.address == "dev/attr"
    assert exc_info.value.timeout_s == 0.05


@pytest.mark.unit
async def test_write_dev_failed_attr_not_allowed_translates_to_write_rejected(
    fake_tango: None,
) -> None:
    port = _make_port(write_raises=_DevFailed(_DevError("API_AttrNotAllowed")))
    with pytest.raises(ControlWriteRejectedError) as exc_info:
        await port.write(_ADDR, 1.0)
    assert exc_info.value.address == "dev/attr"
    assert "API_AttrNotAllowed" in exc_info.value.reason


@pytest.mark.unit
async def test_write_dev_failed_not_writable_translates_to_access_denied(
    fake_tango: None,
) -> None:
    port = _make_port(write_raises=_DevFailed(_DevError("API_AttrNotWritable")))
    with pytest.raises(ControlAccessDeniedError) as exc_info:
        await port.write(_ADDR, 1.0)
    assert exc_info.value.address == "dev/attr"


@pytest.mark.unit
async def test_write_value_error_translates_to_value_coercion(fake_tango: None) -> None:
    port = _make_port(write_raises=ValueError("cannot encode"))
    with pytest.raises(ControlValueCoercionError) as exc_info:
        await port.write(_ADDR, "foo")
    assert exc_info.value.address == "dev/attr"


@pytest.mark.unit
async def test_subscribe_yields_value_then_err_event_raises_through_iterator(
    fake_tango: None,
) -> None:
    """After at least one value, an err-event raises NotConnected through the iterator."""
    port = _make_port(
        events=(
            _EventData(attr_value=_DeviceAttribute(value=1.0)),
            _EventData(err=True),
        )
    )
    iterator = port.subscribe(_ADDR)
    first = await anext(iterator)
    assert first.value == 1.0
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await anext(iterator)
    assert exc_info.value.address == "dev/attr"
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_unsubscribes_on_close(fake_tango: None) -> None:
    """Closing the subscribe iterator calls `unsubscribe_event` with the id."""
    proxy = _FakeProxy(events=(_EventData(attr_value=_DeviceAttribute(value=1.0)),))
    from cora.operation.adapters.tango_control_port import TangoControlPort

    port = TangoControlPort(default_timeout_s=0.05)
    port._proxies["dev"] = proxy  # pyright: ignore[reportPrivateUsage]
    iterator = port.subscribe(_ADDR)
    got = await anext(iterator)
    assert got.value == 1.0
    await iterator.aclose()
    assert proxy.unsubscribed == [7]


@pytest.mark.unit
async def test_aclose_clears_proxies_idempotently(fake_tango: None) -> None:
    port = _make_port(read_result=_DeviceAttribute(value=1.0))
    await port.aclose()
    assert port._proxies == {}  # pyright: ignore[reportPrivateUsage]
    await port.aclose()  # idempotent
    assert port._closed is True  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
def test_require_tango_raises_value_error_when_pytango_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe raises a ValueError (mapped to 422), never an ImportError."""
    from cora.operation.adapters._optional_tango import require_tango

    monkeypatch.setattr(importlib.util, "find_spec", _no_spec)
    with pytest.raises(ValueError, match="PyTango"):
        require_tango("tango")
