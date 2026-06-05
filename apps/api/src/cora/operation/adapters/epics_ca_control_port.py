"""aioca-backed `ControlPort` adapter for production EPICS Channel Access.

Sits in the control-port arc per [[project_control_port_design]] +
[[project_control_port_generalization_research]]. CORA's production
CA client; talks EPICS Channel Access via Diamond Light Source's
`aioca` library (libca via ctypes). Diamond production-uses-it across
their full stack.

`CaprotoControlPort` remains as a parallel test-tier CA client
adapter. Both adapters are integration-tested against the same
`epicscorelibs.ioc` subprocess (see
[[project_control_port_test_isolation_research]]); the test surface
unification lets us verify aioca + caproto behave identically against
real CA wire framing.

PVA goes through p4p (`EpicsPvaControlPort`); CA does not natively
carry NTNDArray (production image streams are PVA-only).

## Connection model

aioca's CA broadcaster reads `EPICS_CA_*` env vars at first use AND
keeps the C-level `ca_context` for the lifetime of the process. The
CA library is process-global (not per-loop). The corpus-canonical
pattern (per the test-isolation research) is:

  - Pin env vars once per worker via session-scoped autouse fixture
    (handled by `tests/integration/conftest.py::_pin_epics_env`).
  - Run the IOC as an external subprocess that outlives the asyncio
    loop (handled by `tests/integration/conftest.py::softioc`).
  - Call `purge_channel_caches()` between tests (handled by
    `_purge_aioca_caches` autouse fixture).

The adapter itself stays simple: no env-var management, no
context-destroy gymnastics. Production deployments set
`EPICS_CA_ADDR_LIST` at process start and never change it.

PVs auto-connect on first `caget` / `camonitor`. We use `cainfo(name)`
as the connection-state precondition at read / write / subscribe entry
so disconnect surfaces cleanly as `ControlNotConnectedError` before
incurring an aioca exception.

## ACL translation (aioca AugmentedValue -> Reading)

`caget(pv, format=FORMAT_TIME)` returns an `AugmentedValue` carrying
the value (numpy-typed for scalars + arrays; `ca_str` for DBR_STRING;
integer index for DBR_ENUM), `.datatype` (CA DBR type code),
`.element_count`, `.timestamp` (Unix epoch float), `.severity` (0-3),
`.status` (alarm status code). The adapter unpacks:

  - `kind`: DBR_ENUM -> "Categorical"; `element_count > 1` -> "Array";
    else "Scalar"
  - `value`: numpy scalars via `.item()`; arrays via
    `tuple(.tolist())`; bytes UTF-8 decoded with `errors="replace"`
  - `quality`: severity 0 -> Good, 1 -> Uncertain, 2/3 -> Bad
  - `quality_detail`: integer status code surfaced as a breadcrumb
    string when severity != NO_ALARM
  - `sampled_at`: `datetime.fromtimestamp(.timestamp, tz=UTC)`

For DBR_ENUM specifically, FORMAT_TIME carries only the integer
index; the adapter widens to FORMAT_CTRL on first encounter to grab
`.enums` for label resolution, then caches the labels per-address so
subsequent reads stay on the cheap FORMAT_TIME path.

## Error mapping

aioca raises ONE exception class, `CANothing(name, errorcode)`,
discriminated by ECA code:

  - `ECA_TIMEOUT` -> `ControlTimeoutError`
  - `ECA_DISCONN` -> `ControlNotConnectedError`
  - `ECA_NORDACCESS` / `ECA_NOWTACCESS` (Access Security read / write
    denial) -> `ControlAccessDeniedError`. These constants are not
    re-exported by `epicscorelibs.ca.cadef`; the encoded values come
    from EPICS Base `caerr.h`: `(msg_no << 3) | severity` with
    `CA_K_WARNING == 0`, giving NORDACCESS=232 and NOWTACCESS=240.
  - caput-callback failure -> `CANothing` with a non-success
    errorcode -> `ControlWriteRejectedError`
  - other ECA codes -> `ControlWriteRejectedError`; the raw
    errorcode folds into the exception detail so the decider's event
    payload captures it per [[project_non_determinism_principle]]

`ControlValueCoercionError` isn't triggered against the softIOC test
fixture (the closed ReadingKind set covers every type the .db
exposes). Retained in the exception family for parity with the port
+ EpicsPva, where p4p's client-side type coercion can raise it.

## Subscribe lifecycle

`subscribe` is a plain `def` returning an async generator directly;
`_assert_connected` + `camonitor` registration both run on the
generator's first `__anext__`. `camonitor(pv, callback, ...)` is
synchronous (returns a `Subscription` object). The callback runs on
the event loop; we pass `asyncio.Queue.put` directly so each update
enqueues without an intermediate Python frame.
`notify_disconnect=True` ensures disconnect arrives as a
`CANothing(.ok=False)` callback rather than a silent stream pause.
The adapter wraps the queue in an async generator so cancellation
runs `sub.close()` via the generator's `finally` (matching the
`CaprotoControlPort` + `InMemoryControlPort` cleanup discipline).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from aioca import (
    DBR_ENUM,
    FORMAT_CTRL,
    FORMAT_TIME,
    CANothing,
    caget,
    cainfo,
    camonitor,
    caput,
)
from epicscorelibs.ca import cadef

from cora.infrastructure.logging import get_logger
from cora.operation._control_dispatch_context import get_dispatch_correlation_id
from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
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


_DEFAULT_TIMEOUT_S = 5.0
"""Default per-operation timeout. aioca's library default is 5s; we
inherit it for production deployments. Tests override with a tighter
value (`default_timeout_s=0.3`) on negative-path tests so a missing
PV fails the test quickly instead of stalling the suite for 5s."""


_ECA_NORDACCESS = 232
_ECA_NOWTACCESS = 240
"""CA Access Security denial errorcodes. `epicscorelibs.ca.cadef`
only re-exports `ECA_TIMEOUT`, `ECA_DISCONN`, `ECA_NORMAL`; the
denial codes come from EPICS Base `caerr.h`:
`(msg_no << CA_K_NCHAR_SHIFT) | severity` with shift=3 and
`CA_K_WARNING == 0`. NORDACCESS uses msg_no=29; NOWTACCESS uses
msg_no=30. Pinned as named constants so `_map_ca_error` reads
declaratively instead of with magic numbers."""


_SEVERITY_TO_QUALITY: dict[int, Quality] = {
    0: "Good",  # NO_ALARM
    1: "Uncertain",  # MINOR_ALARM
    2: "Bad",  # MAJOR_ALARM
    3: "Bad",  # INVALID_ALARM
}


def _quality_for(severity: int) -> Quality:
    return _SEVERITY_TO_QUALITY.get(int(severity), "Bad")


def _kind_for(datatype: int, element_count: int) -> ReadingKind:
    """Map aioca `(datatype, element_count)` to `ReadingKind`.

    aioca normalises FORMAT_TIME / FORMAT_CTRL responses back to the
    base DBR type code, so a single `DBR_ENUM` (= 3) check covers
    every enum variant. Arrays are anything with `element_count > 1`.
    Scalars are everything else.
    """
    if int(datatype) == DBR_ENUM:
        return "Categorical"
    if element_count > 1:
        return "Array"
    return "Scalar"


def _unpack_value(augmented: Any, kind: ReadingKind, enum_labels: tuple[str, ...] | None) -> Any:
    """Extract a Python-native value from aioca's AugmentedValue.

    aioca returns numpy-typed scalars + arrays for numeric DBR types;
    `ca_str` for DBR_STRING; integer index for DBR_ENUM. For enums,
    the adapter resolves the label via `enum_labels` cached from a
    one-shot FORMAT_CTRL read at first encounter.
    """
    if kind == "Categorical":
        index = int(augmented)
        if enum_labels is not None and 0 <= index < len(enum_labels):
            return enum_labels[index]
        return str(index)
    if kind == "Array":
        raw = augmented
        if hasattr(raw, "tolist"):
            return tuple(raw.tolist())
        return tuple(raw)
    scalar: Any = augmented
    if hasattr(scalar, "item"):
        scalar = scalar.item()
    if isinstance(scalar, bytes):
        return scalar.decode("utf-8", errors="replace")
    return scalar


def _quality_detail_for(severity: int, status: int) -> str:
    """Forensic-breadcrumb string for `Reading.quality_detail`.

    aioca exposes `.status` as an integer alarm-status code from
    EPICS's `alarmStatusString` table. For non-NO_ALARM severities
    we surface the integer; the structured-logging layer can resolve
    it to a name. Empty string when severity is NO_ALARM (matches
    the InMemory + Caproto adapters).
    """
    if severity == 0:
        return ""
    return f"alarm_status={int(status)}"


def _to_reading(augmented: Any, enum_labels: tuple[str, ...] | None) -> Reading:
    """Translate an aioca `AugmentedValue` (FORMAT_TIME) to `Reading`."""
    kind = _kind_for(augmented.datatype, augmented.element_count)
    value = _unpack_value(augmented, kind, enum_labels)
    severity = int(getattr(augmented, "severity", 0))
    status = int(getattr(augmented, "status", 0))
    timestamp = float(getattr(augmented, "timestamp", 0.0))
    sampled_at = datetime.fromtimestamp(timestamp, tz=UTC)
    return Reading(
        value=value,
        kind=kind,
        quality=_quality_for(severity),
        sampled_at=sampled_at,
        quality_detail=_quality_detail_for(severity, status),
    )


def _map_ca_error(address: str, exc: CANothing, *, timeout_s: float) -> Exception:
    """Translate `CANothing` errorcodes to the appropriate Control*Error."""
    errorcode = int(getattr(exc, "errorcode", 0))
    if errorcode == cadef.ECA_TIMEOUT:
        return ControlTimeoutError(address, timeout_s)
    if errorcode == cadef.ECA_DISCONN:
        return ControlNotConnectedError(address)
    if errorcode in (_ECA_NORDACCESS, _ECA_NOWTACCESS):
        return ControlAccessDeniedError(address)
    return ControlWriteRejectedError(address, f"CA errorcode={errorcode}")


class EpicsCaControlPort:
    """aioca-backed `ControlPort` implementation. Production CA client.

    See module docstring for the connection model + ACL table.
    """

    def __init__(self, *, default_timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._default_timeout_s = default_timeout_s
        self._enum_labels: dict[str, tuple[str, ...]] = {}
        self._closed = False

    async def _resolve_enum_labels(self, address: str) -> tuple[str, ...] | None:
        """Cache enum labels per address via a one-shot FORMAT_CTRL read."""
        if address in self._enum_labels:
            return self._enum_labels[address]
        try:
            ctrl = await caget(address, format=FORMAT_CTRL, timeout=self._default_timeout_s)
        except CANothing:
            return None
        if int(ctrl.datatype) == DBR_ENUM and hasattr(ctrl, "enums"):
            labels = tuple(ctrl.enums)
            self._enum_labels[address] = labels
            return labels
        return None

    async def _assert_connected(self, address: str) -> None:
        try:
            info = await asyncio.wait_for(cainfo(address), timeout=self._default_timeout_s)
        except (CANothing, TimeoutError) as exc:
            raise ControlNotConnectedError(address) from exc
        if int(info.state) != cadef.cs_conn:
            raise ControlNotConnectedError(address)

    async def read(self, address: str) -> Reading:
        await self._assert_connected(address)
        try:
            augmented = await caget(
                address,
                format=FORMAT_TIME,
                timeout=self._default_timeout_s,
            )
        except CANothing as exc:
            raise _map_ca_error(address, exc, timeout_s=self._default_timeout_s) from exc
        labels: tuple[str, ...] | None = None
        if _kind_for(augmented.datatype, augmented.element_count) == "Categorical":
            labels = await self._resolve_enum_labels(address)
        return _to_reading(augmented, labels)

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
            await self._assert_connected(address)
            await caput(address, value, wait=wait, timeout=timeout_s)
        except CANothing as exc:
            mapped = _map_ca_error(address, exc, timeout_s=timeout_s)
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=type(mapped).__name__,
            )
            raise mapped from exc
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
        iterator's `aclose()`; same pattern as the InMemory + Caproto
        ports. Setup (`_assert_connected` + `camonitor`) runs on the
        generator's first `__anext__`.
        """
        return self._drain(address)

    async def _drain(self, address: str) -> AsyncGenerator[Reading]:
        await self._assert_connected(address)
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sub = camonitor(
            address,
            queue.put,
            format=FORMAT_TIME,
            notify_disconnect=True,
        )
        try:
            labels: tuple[str, ...] | None = None
            while True:
                update = await queue.get()
                if hasattr(update, "ok") and not update.ok:
                    raise ControlNotConnectedError(address)
                if (
                    labels is None
                    and _kind_for(update.datatype, update.element_count) == "Categorical"
                ):
                    labels = await self._resolve_enum_labels(address)
                yield _to_reading(update, labels)
        finally:
            with contextlib.suppress(Exception):
                sub.close()

    async def aclose(self) -> None:
        """Mark the adapter closed + drop the enum-label cache.

        Idempotent. Does NOT call aioca's `purge_channel_caches()` or
        any context-destroy : that responsibility lives at the test
        fixture layer per
        [[project_control_port_test_isolation_research]]; production
        deployments don't need it (the CA broadcaster lives until
        process exit).
        """
        if self._closed:
            return
        self._closed = True
        self._enum_labels.clear()


__all__ = ["EpicsCaControlPort"]
