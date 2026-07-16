"""PyTango-backed `ControlPort` adapter for Tango device attributes.

Sits in the control-port arc per [[project_control_port_design]] +
[[project_control_port_generalization_research]] alongside the EPICS family
(`EpicsCaControlPort`, `EpicsPvaControlPort`). This adapter covers the Tango
substrate that the ESRF BLISS / Beacon deployments (ID19, ID16B, ID28, ID32)
and MAX IV (Tango / Sardana) run on. Value-IO only: Tango Commands (RPC) and
Tango typed events (`DATA_READY` / `INTERFACE_CHANGE`) are out of scope per
the port's anti-hooks and land in future sibling ports.

PyTango (`tango`) binds the C++ Tango core plus omniORB, a heavy native stack
that only Tango-floor deployments need. It ships under the optional `tango`
dependency group and is NOT imported at module load; the adapter probes
importability in `__init__` via `_optional_tango.require_tango` (raising
`ValueError` at wiring, rather than an uncaught `ImportError` mid-loop)
and imports `tango.asyncio` lazily on first use. This keeps `import cora`
cheap on EPICS-only installs.

## Address space

The adapter takes a `TangoAttributeAddress` (already split into `.device` and
`.attribute` by `ControlPortRegistry` via `parse_control_address`). One
`DeviceProxy` is cached per `.device`; many attributes share a device proxy.
The registry does the TRL parsing once at route-match time, so a malformed TRL
fails as a `MalformedControlAddressError` at the boundary rather than here.

## Connection model

`tango.asyncio.DeviceProxy` runs in asyncio green mode: `read_attribute` /
`write_attribute` / `subscribe_event` are awaitable. The proxy constructor is
also awaitable (it pings the device), so it is built lazily inside the async
methods and cached. PyTango has no per-call `timeout=` kwarg on the asyncio
methods, so each call is wrapped in `asyncio.wait_for(..., timeout=...)`; a
`TimeoutError` becomes `ControlTimeoutError` (write) or
`ControlNotConnectedError` (read, where a never-exported device and a slow
device are indistinguishable at this tier, mirroring the p4p adapter).

## ACL translation (Tango DeviceAttribute -> Measurement)

`read_attribute` returns a `DeviceAttribute` carrying `.value`, `.quality`
(`AttrQuality`), `.data_format` (`AttrDataFormat`), `.type` (`CmdArgType`),
and `.time` (`TimeVal`; `.totime()` -> float epoch seconds). The adapter
unpacks:

  - `kind`: `IMAGE` -> "Image"; `SPECTRUM` -> "Array";
    `type == DevEnum` or a `DevState` value -> "Categorical"; else "Scalar".
  - `value`: numpy scalars via `.item()`; spectra via `tuple(...)`; images via
    tuple-of-tuples; `DevEnum` resolved to its label string via the attribute
    config's enum labels, cached per address and falling back to the
    stringified ordinal when the config is unreachable; `DevState` via its
    name (it arrives as a real IntEnum and reports no enum labels). `None`
    whenever the attribute carries no value, which is what an ATTR_INVALID
    read is. A `DevEnum` SPECTRUM stays an `Array` of ordinals: the label
    lookup covers the scalar case only, since a per-element label array has
    no consumer yet.
  - `quality` (`AttrQuality` -> `Quality`): `ATTR_VALID` -> Good;
    `ATTR_WARNING` / `ATTR_CHANGING` -> Uncertain;
    `ATTR_ALARM` / `ATTR_INVALID` -> Bad.
  - `quality_detail`: the raw `AttrQuality` name as a forensic breadcrumb when
    quality is not VALID; empty string when VALID (matches the EPICS adapters).
  - `produced_at`: `datetime.fromtimestamp(attr.time.totime(), tz=UTC)`.

## Error mapping

PyTango raises `tango.DevFailed`, carrying a stack of `DevError` each with a
`.reason` string. The adapter maps the first reason:

  - `API_DeviceTimedOut` / `API_CommandTimedOut` -> `ControlTimeoutError`
  - `API_CantConnectToDevice` / `API_CorbaException` /
    `API_DeviceNotExported` / `API_DeviceNotFound` -> `ControlNotConnectedError`
  - `API_AttrNotAllowed` / `API_WAttrOutsideLimit` -> `ControlWriteRejectedError`
  - `API_AttrNotWritable` and authorisation refusals -> `ControlAccessDeniedError`
  - any other reason -> `ControlWriteRejectedError` with the reason folded into
    the detail so the decider's event payload captures it per
    [[project_non_determinism_principle]]

Client-side value-encode failures (`ValueError` / `TypeError` raised by
PyTango before the wire call) map to `ControlValueCoercionError`.

## Subscribe lifecycle

`subscribe` is a plain `def` returning an async generator directly; proxy
construction + `subscribe_event(attr, EventType.CHANGE_EVENT, cb)` run on the
generator's first `__anext__`. Tango pushes an initial synchronised event on
subscribe, then one per change. The callback receives an `EventData` with
`.attr_value` (a `DeviceAttribute`) and `.err` / `.errors`; it is pushed onto
an unbounded `asyncio.Queue`. An error event raises `ControlNotConnectedError`
through the iterator so a silent stream pause is impossible. The generator's
`finally` calls `unsubscribe_event(event_id)` (matching the EPICS adapters'
cleanup discipline).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false, reportMissingImports=false

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cora.infrastructure.logging import get_logger
from cora.operation._control_dispatch_context import get_dispatch_correlation_id
from cora.operation.adapters._optional_tango import require_tango
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    Measurement,
    MeasurementKind,
    Quality,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.operation.ports.control_address import TangoAttributeAddress


_log = get_logger(__name__)
_DISPATCH_EVENT = "controlport.dispatch"
_DISPATCH_COMPLETED_EVENT = "controlport.dispatch.completed"
_DISPATCH_FAILED_EVENT = "controlport.dispatch.failed"


_DEFAULT_TIMEOUT_S = 5.0
"""Default per-operation timeout. Mirrors the EPICS adapters. Tests override
on negative-path tests (`default_timeout_s=0.3`) so a missing device fails
fast instead of stalling the suite."""


_NOT_CONNECTED_REASONS = frozenset(
    {
        "API_CantConnectToDevice",
        "API_CorbaException",
        "API_DeviceNotExported",
        "API_DeviceNotFound",
    }
)
_TIMEOUT_REASONS = frozenset({"API_DeviceTimedOut", "API_CommandTimedOut"})
_WRITE_REJECTED_REASONS = frozenset({"API_AttrNotAllowed", "API_WAttrOutsideLimit"})
_ACCESS_DENIED_REASONS = frozenset({"API_AttrNotWritable", "API_UnauthorizedAccess"})


def _quality_for(quality: Any) -> Quality:
    """Collapse a Tango `AttrQuality` to the domain `Quality` trichotomy."""
    name = getattr(quality, "name", str(quality))
    if name == "ATTR_VALID":
        return "Good"
    if name in ("ATTR_WARNING", "ATTR_CHANGING"):
        return "Uncertain"
    return "Bad"


def _quality_detail_for(quality: Any) -> str:
    """Forensic-breadcrumb string for `Measurement.quality_detail`.

    Surfaces the raw `AttrQuality` name when quality is not VALID; empty
    string otherwise (matches the EPICS adapters).
    """
    name = getattr(quality, "name", str(quality))
    if name == "ATTR_VALID":
        return ""
    return f"attr_quality={name}"


def _kind_for(attr: Any) -> MeasurementKind:
    """Map a `DeviceAttribute`'s data format + type to `MeasurementKind`."""
    data_format = getattr(attr, "data_format", None)
    format_name = getattr(data_format, "name", str(data_format))
    if format_name == "IMAGE":
        return "Image"
    if format_name == "SPECTRUM":
        return "Array"
    type_name = getattr(getattr(attr, "type", None), "name", "")
    if type_name in ("DevEnum", "DevState"):
        return "Categorical"
    return "Scalar"


def _unpack_value(attr: Any, kind: MeasurementKind, enum_labels: tuple[str, ...] | None) -> Any:
    """Extract a Python-native value from a Tango `DeviceAttribute`.

    Returns `None` when the attribute carries no value, whatever its kind.
    On ATTR_INVALID the Tango core discards the value but keeps
    `data_format`, so an invalid spectrum still classifies as `Array` while
    `attr.value` is `None`: unpacking it as a sequence would raise a bare
    `TypeError` that is not a `ControlPort` error family and so escapes the
    Conductor's closed catch tuple. `None` instead keeps an invalid read
    shaped like every other invalid read (an invalid scalar already reads
    back as `None`), and preserves the forensic pairing of `quality='Bad'`
    with `quality_detail=attr_quality=ATTR_INVALID` that the Conductor
    records against the failed step. Deciding whether a value is usable is
    the consumer's call, not this adapter's: `_require_finite_number`
    already turns a `None` capture into a structured step failure, and a
    check criterion already treats it as a clean mismatch.
    """
    value: Any = getattr(attr, "value", None)
    if value is None:
        return None
    if kind == "Image":
        if hasattr(value, "tolist"):
            return tuple(tuple(row) for row in value.tolist())
        return tuple(tuple(row) for row in value)
    if kind == "Array":
        if hasattr(value, "tolist"):
            return tuple(value.tolist())
        return tuple(value)
    if kind == "Categorical":
        # DevState arrives as a real IntEnum carrying its own label, so it
        # needs no config lookup (and reports no enum_labels). DevEnum
        # arrives as a bare int and is resolved against the cached labels.
        if hasattr(value, "name"):
            return value.name
        index = int(value)
        if enum_labels is not None and 0 <= index < len(enum_labels):
            return enum_labels[index]
        return str(index)
    scalar: Any = value
    if hasattr(scalar, "item"):
        scalar = scalar.item()
    if isinstance(scalar, bytes):
        return scalar.decode("utf-8", errors="replace")
    return scalar


def _to_reading(attr: Any, enum_labels: tuple[str, ...] | None = None) -> Measurement:
    """Translate a Tango `DeviceAttribute` to `Measurement`.

    `enum_labels` resolves a DevEnum ordinal to its label; None leaves the
    ordinal stringified, which is the right fallback for a non-enum or an
    unreachable attribute config.
    """
    kind = _kind_for(attr)
    value = _unpack_value(attr, kind, enum_labels)
    quality = getattr(attr, "quality", None)
    time_val = getattr(attr, "time", None)
    timestamp = time_val.totime() if time_val is not None else 0.0
    produced_at = datetime.fromtimestamp(float(timestamp), tz=UTC)
    return Measurement(
        value=value,
        kind=kind,
        quality=_quality_for(quality),
        produced_at=produced_at,
        quality_detail=_quality_detail_for(quality),
        name=str(getattr(attr, "name", "")),
    )


def _first_reason(exc: Any) -> str:
    """Return the first `DevError.reason` from a `DevFailed`, or empty string."""
    args = getattr(exc, "args", ())
    if args and hasattr(args[0], "reason"):
        return str(args[0].reason)
    return ""


def _map_dev_failed(address: str, exc: Any, *, timeout_s: float) -> Exception:
    """Translate a `tango.DevFailed` to the appropriate Control*Error."""
    reason = _first_reason(exc)
    if reason in _TIMEOUT_REASONS:
        return ControlTimeoutError(address, timeout_s)
    if reason in _NOT_CONNECTED_REASONS:
        return ControlNotConnectedError(address)
    if reason in _ACCESS_DENIED_REASONS:
        return ControlAccessDeniedError(address)
    if reason in _WRITE_REJECTED_REASONS:
        return ControlWriteRejectedError(address, reason)
    return ControlWriteRejectedError(address, reason or "DevFailed")


class TangoControlPort:
    """PyTango-backed `ControlPort` implementation for Tango device attributes.

    See module docstring for the connection model, ACL table, error
    mapping, and subscribe lifecycle. Probes PyTango importability at
    construction so a missing `tango` extra fails as a `ValueError` at
    wiring time, not as an `ImportError` mid-conduct.
    """

    def __init__(self, *, default_timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        require_tango("tango")
        self._default_timeout_s = default_timeout_s
        self._proxies: dict[str, Any] = {}
        self._enum_labels: dict[str, tuple[str, ...]] = {}
        self._closed = False

    async def _resolve_enum_labels(self, address: TangoAttributeAddress) -> tuple[str, ...] | None:
        """Cache a DevEnum attribute's labels per address via its attribute config.

        Mirrors `EpicsCaControlPort._resolve_enum_labels`. Labels live in the
        attribute CONFIG, never on the read value, so this costs one extra
        round trip at first encounter; caching keeps it off the conduct
        loop's per-read path, where on a real Tango network (unlike
        loopback) it would be a real CORBA call per read.

        An empty tuple is cached and returned as None, meaning "not an enum".
        Caching that negative matters here in a way it does not for EPICS:
        `DevState` is a common Categorical that reports NO labels, so
        without it every DevState read would re-fetch the config forever.
        A config fetch that fails is not an error worth raising: the read
        itself already succeeded, so fall back to the ordinal rather than
        turn a readable attribute into a failed step.
        """
        from tango import DevFailed

        raw = str(address)
        cached = self._enum_labels.get(raw)
        if cached is not None:
            return cached or None
        try:
            proxy = await self._proxy_for(address.device)
            config = await asyncio.wait_for(
                proxy.get_attribute_config(address.attribute),
                timeout=self._default_timeout_s,
            )
        except (TimeoutError, DevFailed):
            return None
        labels = tuple(str(label) for label in getattr(config, "enum_labels", ()))
        self._enum_labels[raw] = labels
        return labels or None

    async def _proxy_for(self, device: str) -> Any:
        """Return a cached asyncio `DeviceProxy` for `device`, building it lazily.

        The asyncio proxy constructor is awaitable (it pings the device on
        build), so a construction failure surfaces here as `DevFailed` and
        is mapped by the caller.
        """
        proxy = self._proxies.get(device)
        if proxy is None:
            from tango.asyncio import DeviceProxy

            # `tango.asyncio.DeviceProxy` is a partial over `get_device_proxy`
            # whose declared return does not vary with green mode, so it types
            # as a bare DeviceProxy. Under Asyncio it really returns an
            # awaitable, which the integration module proves: `wait_for` on a
            # non-awaitable would raise TypeError instead of passing.
            proxy = await asyncio.wait_for(
                DeviceProxy(device),  # pyright: ignore[reportArgumentType]
                timeout=self._default_timeout_s,
            )
            self._proxies[device] = proxy
        return proxy

    async def read(self, address: TangoAttributeAddress) -> Measurement:
        from tango import DevFailed

        raw = str(address)
        try:
            proxy = await self._proxy_for(address.device)
            attr = await asyncio.wait_for(
                proxy.read_attribute(address.attribute), timeout=self._default_timeout_s
            )
        except TimeoutError as exc:
            raise ControlNotConnectedError(raw) from exc
        except DevFailed as exc:
            raise _map_dev_failed(raw, exc, timeout_s=self._default_timeout_s) from exc
        enum_labels: tuple[str, ...] | None = None
        if _kind_for(attr) == "Categorical":
            enum_labels = await self._resolve_enum_labels(address)
        return _to_reading(attr, enum_labels)

    async def write(
        self,
        address: TangoAttributeAddress,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        from tango import DevFailed

        _ = wait  # Tango writes are synchronous-confirmed; no fire-and-forget arm.
        raw = str(address)
        correlation_id = get_dispatch_correlation_id()
        _log.info(
            _DISPATCH_EVENT,
            address=raw,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="started",
        )
        try:
            proxy = await self._proxy_for(address.device)
            await asyncio.wait_for(
                proxy.write_attribute(address.attribute, value), timeout=timeout_s
            )
        except TimeoutError as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=raw,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlTimeoutError.__name__,
            )
            raise ControlTimeoutError(raw, timeout_s) from exc
        except DevFailed as exc:
            mapped = _map_dev_failed(raw, exc, timeout_s=timeout_s)
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=raw,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=type(mapped).__name__,
            )
            raise mapped from exc
        except (ValueError, TypeError) as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=raw,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlValueCoercionError.__name__,
            )
            raise ControlValueCoercionError(
                raw, raw_type=type(value).__name__, target_kind="tango write"
            ) from exc
        _log.info(
            _DISPATCH_COMPLETED_EVENT,
            address=raw,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="completed",
        )

    def subscribe(self, address: TangoAttributeAddress) -> AsyncGenerator[Measurement]:
        """Return type narrows the Protocol's `AsyncIterator` to `AsyncGenerator`.

        Covariant return lets tests close subscriptions via the iterator's
        `aclose()`; same pattern as the EPICS adapters. Setup (proxy build +
        `subscribe_event`) runs on the generator's first `__anext__`.
        """
        return self._drain(address)

    async def _drain(self, address: TangoAttributeAddress) -> AsyncGenerator[Measurement]:
        from tango import DevFailed, EventType

        raw = str(address)
        queue: asyncio.Queue[Any] = asyncio.Queue()

        def _callback(event: Any) -> None:
            # Synchronous put_nowait keeps FIFO ordering across rapid events;
            # the queue is unbounded so it never raises QueueFull.
            queue.put_nowait(event)

        try:
            proxy = await self._proxy_for(address.device)
            event_id = await asyncio.wait_for(
                proxy.subscribe_event(address.attribute, EventType.CHANGE_EVENT, _callback),
                timeout=self._default_timeout_s,
            )
        except TimeoutError as exc:
            raise ControlNotConnectedError(raw) from exc
        except DevFailed as exc:
            raise _map_dev_failed(raw, exc, timeout_s=self._default_timeout_s) from exc

        try:
            while True:
                event = await queue.get()
                if getattr(event, "err", False):
                    raise ControlNotConnectedError(raw)
                attr = getattr(event, "attr_value", None)
                if attr is None:
                    continue
                enum_labels: tuple[str, ...] | None = None
                if _kind_for(attr) == "Categorical":
                    enum_labels = await self._resolve_enum_labels(address)
                yield _to_reading(attr, enum_labels)
        finally:
            with contextlib.suppress(Exception):
                await proxy.unsubscribe_event(event_id)

    async def aclose(self) -> None:
        """Drop cached device proxies + enum labels; idempotent.

        Tango `DeviceProxy` objects release their CORBA connection on
        garbage collection; dropping the cache is sufficient. The enum-label
        cache goes with them so a reopened port re-reads attribute config
        rather than trusting labels from before a device restart. Provided so
        production code paths can call `aclose()` polymorphically against any
        `ControlPort`.
        """
        if self._closed:
            return
        self._closed = True
        self._proxies.clear()
        self._enum_labels.clear()


__all__ = ["TangoControlPort"]
