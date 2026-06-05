"""caproto-backed `ControlPort` adapter for the integration test tier.

Per [[project_control_port_design]] § Test surface and
[[project_control_port_generalization_research]], caproto is CORA's
integration-tier substrate ONLY. The same Python package serves both
client and server roles: this adapter is the CA client; the
`caproto_ioc` pytest fixture spins up the IOC. Both run in-process
inside the same pytest worker.

The maintainers' own README warns: "applications requiring battle-
tested reliability (their example: running an accelerator) should
steer well clear." Production CA traffic goes through aioca
(`EpicsCaControlPort`); PVA goes through p4p (`EpicsPvaControlPort`).
This adapter exists to exercise the `ControlPort` Protocol against
real CA wire framing without testcontainers / softIOC binaries /
EPICS Base system installation.

## Connection model

`Context()` is created lazily on first `read` / `write` / `subscribe`
call to ensure it runs inside the active event loop (caproto reads
`EPICS_CA_*` env vars at broadcaster init, so the `caproto_ioc`
fixture's monkeypatch must already have applied). PVs are resolved
once via `Context.get_pvs` and cached per-address; reconnect is
caproto's responsibility (its background broadcaster reissues
searches on disconnect).

## ACL translation (caproto -> Reading)

`pv.read(data_type="time", ...)` returns a `ReadNotifyResponse`
carrying `data` (numpy array, shape `(count,)` even for scalars),
`data_type` (TIME_<base> ChannelType), `data_count`, and `metadata`
(timestamp + alarm severity + alarm status). The adapter unpacks:

  - `kind` from `caproto.native_type(data_type)`:
      enum types -> "Categorical"
      data_count > 1 -> "Array"
      otherwise -> "Scalar"
  - `value` unwrapped from the numpy array (scalar at index 0 with
    `.item()`; bytes decoded UTF-8 with `errors="replace"` so a
    non-UTF-8 IOC string never escapes as `UnicodeDecodeError`
    outside the declared 6-exception family; tuple for arrays)
  - `quality` from `metadata.severity`:
      NO_ALARM -> "Good"
      MINOR_ALARM -> "Uncertain"
      MAJOR_ALARM / INVALID_ALARM -> "Bad"
  - `quality_detail` as `f"alarm_status={int(status)}"` when severity
    is non-NO_ALARM (forensic breadcrumb; matches EpicsCa + EpicsPva
    format so consumers can parse one shape across CA / PVA / future
    substrates without per-adapter casing)
  - `sampled_at` from `metadata.stamp.as_datetime()`, UTC-coerced

## Error mapping

  - `wait_for_connection` timeout -> `ControlNotConnectedError`
  - `pv.read` / `pv.write` timeout -> `ControlTimeoutError`
  - `pv.write` IOC-side rejection -> `ControlWriteRejectedError`
    (caproto raises `ErrorResponseReceived` carrying the EPICS-side
    error message)

`ControlAccessDeniedError` and `ControlValueCoercionError` are
declared in the port but not yet triggered by this adapter: CA
Access Security isn't configured on the test IOC, and the closed
ReadingKind set covers every type our test IOC exposes. Both stay
in the exception family for parity with production adapters where
they DO fire (`EpicsCaControlPort` / `EpicsPvaControlPort`).

## Subscribe lifecycle

`subscribe` is a plain `def` returning an async generator directly;
connect + PV-resolve + `pv.subscribe(...)` all run on the
generator's first `__anext__`. `pv.subscribe(...)` returns a
`Subscription` whose `async for` yields `SubscriptionData` carrying
the same fields as a read response. The adapter wraps this in an
async generator so cancellation runs `sub.clear()` via the
generator's `finally` (matching the `InMemoryControlPort` cleanup
discipline).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import caproto
from caproto import (
    AlarmSeverity,
    CaprotoError,
    CaprotoTimeoutError,
    ChannelType,
    ErrorResponseReceived,
)
from caproto.asyncio.client import Context

from cora.infrastructure.logging import get_logger
from cora.operation._control_dispatch_context import get_dispatch_correlation_id
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlWriteRejectedError,
    Quality,
    Reading,
    ReadingKind,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


_log = get_logger(__name__)
_DISPATCH_EVENT = "controlport.dispatch"
_DISPATCH_COMPLETED_EVENT = "controlport.dispatch.completed"
_DISPATCH_FAILED_EVENT = "controlport.dispatch.failed"


_DEFAULT_TIMEOUT_S = 2.0
"""Default per-operation timeout. Integration tests run on loopback
inside the same process as the IOC; 2 seconds is generous. Production
adapters (`EpicsCaControlPort`, `EpicsPvaControlPort`) pick
deployment-appropriate defaults."""


_SEVERITY_TO_QUALITY: dict[AlarmSeverity, Quality] = {
    AlarmSeverity.NO_ALARM: "Good",
    AlarmSeverity.MINOR_ALARM: "Uncertain",
    AlarmSeverity.MAJOR_ALARM: "Bad",
    AlarmSeverity.INVALID_ALARM: "Bad",
}


def _quality_for(severity: AlarmSeverity | int) -> Quality:
    try:
        return _SEVERITY_TO_QUALITY[AlarmSeverity(severity)]
    except (ValueError, KeyError):
        return "Bad"


def _kind_for(data_type: int, data_count: int) -> ReadingKind:
    """Map caproto `(data_type, data_count)` to `ReadingKind`.

    Enum types collapse to `Categorical` regardless of count (CA
    enum waveforms are rare and would still represent discrete labels).
    Arrays are anything with count > 1. Scalars are everything else.
    """
    ct = ChannelType(data_type)
    if ct in caproto.enum_types:
        return "Categorical"
    if data_count > 1:
        return "Array"
    return "Scalar"


def _unpack_value(data: Any, kind: ReadingKind) -> Any:
    """Extract a Python-native value from caproto's numpy-array data.

    Scalars come back as length-1 arrays; arrays as length-N; strings
    as bytes that need UTF-8 decoding (with `errors="replace"` so a
    rogue IOC string never escapes as `UnicodeDecodeError` outside the
    declared 6-exception family).
    """
    if kind == "Array":
        return tuple(data.tolist()) if hasattr(data, "tolist") else tuple(data)
    if len(data) == 0:
        return None
    scalar: Any = data[0]
    if hasattr(scalar, "item"):
        scalar = scalar.item()
    if isinstance(scalar, bytes):
        return scalar.decode("utf-8", errors="replace")
    return scalar


def _to_reading(response: Any) -> Reading:
    """Translate a caproto `ReadNotifyResponse` (or subscription update) to `Reading`."""
    kind = _kind_for(response.data_type, response.data_count)
    value = _unpack_value(response.data, kind)

    metadata = response.metadata
    severity = getattr(metadata, "severity", AlarmSeverity.NO_ALARM)
    quality = _quality_for(severity)

    quality_detail = ""
    if severity != AlarmSeverity.NO_ALARM:
        status = getattr(metadata, "status", None)
        if status is not None:
            quality_detail = f"alarm_status={int(status)}"

    stamp = getattr(metadata, "stamp", None)
    if stamp is not None and hasattr(stamp, "as_datetime"):
        sampled_at = stamp.as_datetime()
        if sampled_at.tzinfo is None:
            sampled_at = sampled_at.replace(tzinfo=UTC)
    else:
        sampled_at = datetime.now(tz=UTC)

    return Reading(
        value=value,
        kind=kind,
        quality=quality,
        sampled_at=sampled_at,
        quality_detail=quality_detail,
    )


class CaprotoControlPort:
    """caproto-backed `ControlPort` implementation.

    Test-tier only. See module docstring for the why + the ACL
    translation table.
    """

    def __init__(self, *, default_timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._context: Context | None = None
        self._pvs: dict[str, Any] = {}
        self._default_timeout_s = default_timeout_s

    async def _ensure_context(self) -> Context:
        if self._context is None:
            self._context = Context()
        return self._context

    async def _resolve_pv(self, address: str) -> Any:
        cached = self._pvs.get(address)
        if cached is not None:
            return cached
        ctx = await self._ensure_context()
        (pv,) = await ctx.get_pvs(address)
        self._pvs[address] = pv
        return pv

    async def _connected_pv(self, address: str) -> Any:
        pv = await self._resolve_pv(address)
        try:
            await pv.wait_for_connection(timeout=self._default_timeout_s)
        except (CaprotoTimeoutError, CaprotoError) as exc:
            raise ControlNotConnectedError(address) from exc
        return pv

    async def read(self, address: str) -> Reading:
        pv = await self._connected_pv(address)
        try:
            response = await pv.read(data_type="time", timeout=self._default_timeout_s)
        except CaprotoTimeoutError as exc:
            raise ControlTimeoutError(address, self._default_timeout_s) from exc
        return _to_reading(response)

    async def write(
        self,
        address: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        correlation_id = get_dispatch_correlation_id()
        _log.info(
            _DISPATCH_EVENT,
            address=address,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="started",
        )
        try:
            pv = await self._connected_pv(address)
            await pv.write(value, wait=wait, timeout=timeout_s)
        except CaprotoTimeoutError as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlTimeoutError.__name__,
            )
            raise ControlTimeoutError(address, timeout_s) from exc
        except ErrorResponseReceived as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlWriteRejectedError.__name__,
            )
            raise ControlWriteRejectedError(address, str(exc)) from exc
        except ControlNotConnectedError:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlNotConnectedError.__name__,
            )
            raise
        _log.info(
            _DISPATCH_COMPLETED_EVENT,
            address=address,
            operation="write",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            status="completed",
        )

    def subscribe(self, address: str) -> AsyncGenerator[Reading]:
        """Return type narrows the Protocol's `AsyncIterator` to `AsyncGenerator`.

        Covariant return lets tests close subscriptions via the
        iterator's `aclose()` while production callers still see the
        `AsyncIterator` contract through the Protocol surface; same
        pattern as `InMemoryControlPort.subscribe`. Setup (PV resolve
        + connect + `pv.subscribe`) runs on the generator's first
        `__anext__`.
        """
        return self._drain(address)

    async def _drain(self, address: str) -> AsyncGenerator[Reading]:
        pv = await self._connected_pv(address)
        sub = pv.subscribe(data_type="time")
        try:
            async for response in sub:
                yield _to_reading(response)
        finally:
            with contextlib.suppress(CaprotoError):
                await sub.clear()

    async def aclose(self) -> None:
        """Disconnect the underlying caproto Context + drop the PV cache.

        Tests SHOULD call this on teardown to avoid background-task
        leaks across the suite. Idempotent: a second call is a no-op.
        """
        if self._context is None:
            return
        with contextlib.suppress(CaprotoError):
            await self._context.disconnect()
        self._context = None
        self._pvs.clear()


__all__ = ["CaprotoControlPort"]
