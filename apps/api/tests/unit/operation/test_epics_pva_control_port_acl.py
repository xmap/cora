"""Unit-tier ACL tests for `EpicsPvaControlPort` error mapping.

Mirrors `test_epics_ca_control_port_acl.py`. The `pv.read` / `pv.write`
timeout + remote-rejection ACL arms can't be exercised against the
softIOC fixture (no native slow-getter; the softIOC accepts every
write to its standard records). This file covers the branches with
monkey-patched p4p `Context` methods raising the appropriate
exceptions; the adapter's error-translation is pinned end-to-end.

Coverage:

  - `asyncio.TimeoutError` on read -> `ControlNotConnectedError`
    (PVA can't distinguish slow-IOC from never-connected on the read
    path; both surface via wait_for's TimeoutError)
  - `asyncio.TimeoutError` on write -> `ControlTimeoutError`
    (writes only fire after a successful connect, so timeout here is
    unambiguously slow-IOC)
  - `Disconnected` on read -> `ControlNotConnectedError`
  - `RemoteError` on write -> `ControlWriteRejectedError`
  - `ValueError` on write -> `ControlValueCoercionError`
  - mid-stream `Disconnected` on subscribe (after first value) ->
    NotConnected through the iterator (the `seen_value=True` branch
    in `_drain`; softIOC's monitor stays open silently so this can't
    be reached at the integration tier)
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

import asyncio
from typing import Any

import pytest
from p4p.client.asyncio import Disconnected, RemoteError

from cora.operation.adapters.epics_pva_control_port import EpicsPvaControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
)


class _FakeContext:
    """Stand-in `p4p.client.asyncio.Context` with programmable `get` / `put` outcomes.

    Constructed with an `outcome` exception that each method raises.
    Provides the same `close()` shape the adapter calls on aclose.
    """

    def __init__(
        self,
        *,
        get_raises: type[Exception] | None = None,
        put_raises: type[Exception] | None = None,
        raise_value: Any = None,
    ) -> None:
        self._get_raises = get_raises
        self._put_raises = put_raises
        self._raise_value = raise_value
        self.closed = False

    async def get(self, address: str, request: str = "") -> Any:
        _ = (address, request)
        if self._get_raises is not None:
            if self._raise_value is not None:
                raise self._get_raises(self._raise_value)
            raise self._get_raises()
        return None

    async def put(self, address: str, value: Any, wait: bool = True) -> None:
        _ = (address, value, wait)
        if self._put_raises is not None:
            if self._raise_value is not None:
                raise self._put_raises(self._raise_value)
            raise self._put_raises()

    def close(self) -> None:
        self.closed = True


def _hijack_context(port: EpicsPvaControlPort, ctx: Any) -> None:
    """Inject a fake `Context` so the adapter's lazy `_ensure_context` returns it."""
    port._context = ctx  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_read_translates_asyncio_timeout_to_not_connected() -> None:
    """`asyncio.TimeoutError` on `ctx.get` surfaces as `ControlNotConnectedError`.

    PVA has no separate not-found exception; a never-connected PV and
    a slow-IOC read both surface the same way at this tier. The unit-
    tier test deliberately exercises the timeout path.
    """
    port = EpicsPvaControlPort(default_timeout_s=0.05)
    _hijack_context(port, _FakeContext(get_raises=asyncio.TimeoutError))
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read("test_pv")
    assert exc_info.value.address == "test_pv"


@pytest.mark.unit
async def test_read_translates_disconnected_to_not_connected() -> None:
    """`Disconnected` raised by `ctx.get` surfaces as `ControlNotConnectedError`."""
    port = EpicsPvaControlPort()
    _hijack_context(port, _FakeContext(get_raises=Disconnected))
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read("test_pv")
    assert exc_info.value.address == "test_pv"


@pytest.mark.unit
async def test_write_translates_asyncio_timeout_to_control_timeout_error() -> None:
    """`asyncio.TimeoutError` on `ctx.put` surfaces as `ControlTimeoutError`.

    On the write path the timeout is unambiguously slow-IOC, so it
    maps to `ControlTimeoutError` (vs the read path's NotConnected).
    """
    port = EpicsPvaControlPort()
    _hijack_context(port, _FakeContext(put_raises=asyncio.TimeoutError))
    with pytest.raises(ControlTimeoutError) as exc_info:
        await port.write("test_pv", 1.0, timeout_s=0.05)
    assert exc_info.value.address == "test_pv"
    assert exc_info.value.timeout_s == 0.05


@pytest.mark.unit
async def test_write_translates_remote_error_to_write_rejected() -> None:
    """`RemoteError` (server PUT rejection) surfaces as `ControlWriteRejectedError`."""
    port = EpicsPvaControlPort()
    _hijack_context(port, _FakeContext(put_raises=RemoteError, raise_value="IOC says no"))
    with pytest.raises(ControlWriteRejectedError) as exc_info:
        await port.write("test_pv", 1.0)
    assert exc_info.value.address == "test_pv"
    assert "IOC says no" in exc_info.value.reason


@pytest.mark.unit
async def test_write_translates_value_error_to_value_coercion() -> None:
    """`ValueError` (client-side type-coercion failure) surfaces as `ControlValueCoercionError`."""
    port = EpicsPvaControlPort()
    _hijack_context(
        port,
        _FakeContext(put_raises=ValueError, raise_value="cannot coerce 'foo' to int"),
    )
    with pytest.raises(ControlValueCoercionError) as exc_info:
        await port.write("test_pv", "foo")
    assert exc_info.value.address == "test_pv"


@pytest.mark.unit
async def test_aclose_closes_context_idempotently() -> None:
    """First aclose() closes the Context; second call is a no-op."""
    port = EpicsPvaControlPort()
    fake = _FakeContext()
    _hijack_context(port, fake)
    await port.aclose()
    assert fake.closed is True
    await port.aclose()  # idempotent
    assert port._closed is True  # pyright: ignore[reportPrivateUsage]


class _FakeValue(float):
    """Stand-in for an augmented `ntfloat` carrying alarm + timestamp metadata.

    Subclassing `float` mimics p4p's `NTScalar(float)` augmented type;
    the `raw` attribute returns None so `_classify_kind` lands on
    `"Scalar"` and `_unpack_value` returns the float verbatim. Enough
    surface for `_to_reading` to produce a valid Measurement without a
    live PVA channel.
    """

    raw = None
    severity = 0
    status = 0
    timestamp = 0.0


class _MonitorContext:
    """Fake p4p Context whose `monitor` invokes its callback synchronously."""

    def __init__(self, *updates: Any) -> None:
        self._updates = updates
        self._closed = False
        self._pending: list[asyncio.Future[Any]] = []

    def monitor(self, _address: str, callback: Any, **_kwargs: Any) -> Any:
        for update in self._updates:
            self._pending.append(asyncio.ensure_future(callback(update)))
        return _FakeSubscription()

    def close(self) -> None:
        self._closed = True


class _FakeSubscription:
    def close(self) -> None:  # pragma: no cover - finally suppress only
        pass

    async def wait_closed(self) -> None:  # pragma: no cover - finally suppress only
        return None


@pytest.mark.unit
async def test_subscribe_mid_stream_disconnect_raises_through_iterator() -> None:
    """After at least one value, a `Disconnected` update raises NotConnected.

    Pins the `seen_value=True` branch in `_drain` that the integration
    fixture cannot exercise: the softIOC's monitor stays open silently
    on a disconnect, so there is no live `Disconnected` event to feed
    back through. Monkey-patches `Context.monitor` to invoke its
    callback with a value followed by a `Disconnected`, both scheduled
    on the loop so the adapter's `await queue.get()` resolves.
    """
    port = EpicsPvaControlPort()
    _hijack_context(port, _MonitorContext(_FakeValue(1.0), Disconnected()))
    iterator = port.subscribe("test_pv")
    first = await anext(iterator)
    assert first.value == 1.0
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await anext(iterator)
    assert exc_info.value.address == "test_pv"
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_initial_disconnect_is_ignored_then_value_yields() -> None:
    """Pre-value `Disconnected` is silently consumed; the first value still arrives.

    Initial-state-Disconnected fires before p4p completes channel
    discovery; the adapter swallows it (the `seen_value=False` branch)
    and waits for the first real value. The integration fixture would
    skip this branch if monitor always opens cleanly.
    """
    port = EpicsPvaControlPort()
    _hijack_context(port, _MonitorContext(Disconnected(), _FakeValue(2.5)))
    iterator = port.subscribe("test_pv")
    got = await anext(iterator)
    assert got.value == 2.5
    await iterator.aclose()
