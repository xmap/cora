"""p4p-backed `ControlPort` adapter for production EPICS pvAccess.

Sits in the control-port arc per [[project_control_port_design]] +
[[project_control_port_generalization_research]] +
[[project_control_port_test_isolation_research]]. Production PVA client
(p4p / pvxs; EPICS Base official); talks EPICS V4 Normative Types end
to end.

`EpicsCaControlPort` (aioca) is the parallel production CA client;
together they cover the EPICS substrate. PVA adds what CA cannot
carry: NTNDArray (structured 2-D image streams) which surface as the
`Image` ReadingKind. The existing `epicscorelibs.ioc` softIOC auto-
loads qsrv + pvAccessIOC, so both the CA adapter (aioca via CA) and
this PVA adapter (p4p via PVA) integration-test against the same
subprocess fixture.

## Connection model

p4p's `Context(provider='pva')` owns its own per-instance channel
cache: no process-global broadcaster state, no `purge_channel_caches`
analog needed at the fixture layer. The adapter constructs one
`Context` lazily on first call and `close()`s it in `aclose()`.
This is a cleaner per-test isolation story than aioca's; tests can
spin up adapter instances freely without cross-contamination.

p4p's `Context` methods have NO native `timeout=` kwarg. CORA wraps
each call in `asyncio.wait_for(..., timeout=self._default_timeout_s)`
so `asyncio.TimeoutError` becomes `ControlTimeoutError` (read / write)
or `ControlNotConnectedError` (when the PV never exists; p4p has no
separate not-found exception). The same `wait_for` wrapping also
handles the precondition check that aioca's `cainfo` provides
implicitly.

## ACL translation (p4p Value / NT subclass -> Reading)

`Context.get(name)` returns an augmented NT Python object that carries
flattened `.timestamp` (float seconds UTC), `.severity` (int 0-3),
`.status` (int), and `.raw` (the underlying `p4p.Value`). The adapter
unpacks per NT type:

  - `NTScalar` -> `Reading(kind="Scalar")`, `value = `int / float / str
    via the augmented subclass (e.g., `int(ntint)`)
  - `NTScalarArray` -> `Reading(kind="Array")`, `value = tuple(...)`
  - `NTNDArray` -> `Reading(kind="Image")`, `value = ((...,)*n)` tuple
    of tuples (the augmented `ntndarray` is already shape-correct;
    dimension reshape is applied by the NT unwrap)
  - `NTEnum` -> `Reading(kind="Categorical")`, `value = ` label string
    resolved via `raw['value.choices'][int(...)]`
  - `NTTable` -> `Reading(kind="Tabular")`, `value = ` dict of
    column-name -> tuple (rare in practice; reserved for future use)

`quality` from `severity` via the same 0->Good, 1->Uncertain, 2/3->Bad
map the CA adapter uses. `quality_detail` from `status` integer as a
forensic breadcrumb when severity is non-zero.

`Context.get` is called with `request="field(value,alarm,timeStamp,
dimension)"` so the response carries the metadata we need without
the full presentation hint surface.

## Error mapping

  - `asyncio.TimeoutError` (from `wait_for`) on read / subscribe ->
    `ControlNotConnectedError` (the PV never resolved within the
    deadline; p4p surfaces this same way for both never-connected
    AND read-timeout-on-a-connected-PV, so we treat the negative-
    path tests at the unit tier where the disambiguation matters)
  - `asyncio.TimeoutError` on write -> `ControlTimeoutError(address,
    timeout_s)` (write-side timeouts are unambiguously slow-IOC, not
    not-found)
  - `p4p.client.asyncio.Disconnected` (from monitor callback) ->
    `ControlNotConnectedError`
  - `p4p.client.asyncio.RemoteError` (server-side put rejection) ->
    `ControlWriteRejectedError`
  - `ValueError` (p4p client-side type coercion failure on put) ->
    `ControlValueCoercionError`

`ControlAccessDeniedError` isn't triggered by the softIOC test fixture
(no Access Security configured at the PVA layer). Retained in the
exception family for parity.

## Subscribe lifecycle

`subscribe` is a plain `def` returning an async generator directly;
context-construct + `ctx.monitor` registration both run on the
generator's first `__anext__`.
`Context.monitor(name, callback, notify_disconnect=True)` is
SYNCHRONOUS and returns a `Subscription` immediately. The callback
fires from p4p's internal thread; p4p detects async-def callbacks
and schedules them on the running loop, so we pass an inline async
function that puts onto an `asyncio.Queue`. The adapter wraps the
queue in an async generator so cancellation runs `sub.close() +
sub.wait_closed()` via the generator's `finally` (matching the
CaprotoControlPort + EpicsCaControlPort + InMemoryControlPort
cleanup discipline).

`Disconnected` arriving on the queue raises
`ControlNotConnectedError` through the iterator so the consumer can
decide to re-subscribe.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from p4p.client.asyncio import Context, Disconnected, RemoteError

from cora.infrastructure.logging import get_logger
from cora.operation._control_dispatch_context import get_dispatch_correlation_id
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
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
"""Default per-operation timeout. Mirrors the CA adapter.
Tests override on negative-path tests (`default_timeout_s=0.3`)."""


_FIELD_REQUEST = "field(value,alarm,timeStamp,dimension)"
"""PVA field selector. Restricts the server response to the fields
the adapter ACL needs: the value plus alarm + timestamp metadata,
plus `dimension` so NTNDArray's shape comes through. Avoids
transferring `display`, `control`, `valueAlarm` presentation hints."""


_SEVERITY_TO_QUALITY: dict[int, Quality] = {
    0: "Good",  # NO_ALARM
    1: "Uncertain",  # MINOR_ALARM
    2: "Bad",  # MAJOR_ALARM
    3: "Bad",  # INVALID_ALARM
}


def _quality_for(severity: int) -> Quality:
    return _SEVERITY_TO_QUALITY.get(int(severity), "Bad")


def _quality_detail_for(severity: int, status: int) -> str:
    """Forensic-breadcrumb string for `Reading.quality_detail`.

    p4p exposes `.status` as an integer alarm-status code (same shape
    as aioca's). Empty when severity is NO_ALARM (matches the
    InMemory + Caproto + EpicsCa adapters).
    """
    if severity == 0:
        return ""
    return f"alarm_status={int(status)}"


def _classify_kind(value: Any) -> ReadingKind:
    """Decide ReadingKind from the NT type ID embedded in the raw Value.

    p4p's augmented Python subclasses expose the underlying `Value`
    via `.raw`. The Value's `.getID()` returns the structure ID like
    `epics:nt/NTScalar:1.0`. We branch on this rather than on Python
    type because NTNDArray's augmented subclass is a numpy subclass
    too, so isinstance checks against numpy.ndarray would be
    ambiguous.
    """
    raw = getattr(value, "raw", None)
    if raw is None:
        return "Scalar"
    type_id = raw.getID() if hasattr(raw, "getID") else ""
    if "NTNDArray" in type_id:
        return "Image"
    if "NTEnum" in type_id:
        return "Categorical"
    if "NTTable" in type_id:
        return "Tabular"
    if "NTScalarArray" in type_id:
        return "Array"
    return "Scalar"


def _unpack_value(value: Any, kind: ReadingKind) -> Any:
    """Extract a Python-native value from p4p's augmented NT object."""
    if kind == "Image":
        # The augmented ntndarray subclass is a numpy array shaped per
        # the NTNDArray dimensions (Fortran-order reshape applied by
        # the NT unwrap layer). Convert to tuple-of-tuples for the
        # Reading dataclass; Python-native + hashable.
        if hasattr(value, "tolist"):
            return tuple(tuple(row) for row in value.tolist())
        return tuple(value)
    if kind == "Categorical":
        raw = getattr(value, "raw", None)
        choices: tuple[str, ...] = ()
        if raw is not None:
            try:
                choices = tuple(raw["value.choices"])
            except (KeyError, TypeError):
                choices = ()
        index = int(value)
        if 0 <= index < len(choices):
            return choices[index]
        return str(index)
    if kind == "Tabular":
        # NTTable iterates as OrderedDicts per row when unwrapped;
        # for the Reading dataclass we materialise to a column-oriented
        # dict of tuples so the value stays hashable + comparable.
        rows = list(value)
        if not rows:
            return {}
        columns: dict[str, list[Any]] = {col: [] for col in rows[0]}
        for row in rows:
            for col, val in row.items():
                columns[col].append(val)
        return {col: tuple(vals) for col, vals in columns.items()}
    if kind == "Array":
        if hasattr(value, "tolist"):
            return tuple(value.tolist())
        return tuple(value)
    # Scalar
    raw_value: Any = value
    if isinstance(raw_value, bytes):
        return raw_value.decode("utf-8", errors="replace")
    # Augmented NTScalar subclasses (ntfloat / ntint / ntstr) coerce
    # cleanly via their parent type's __new__ semantics; just return.
    return raw_value


def _to_reading(value: Any) -> Reading:
    """Translate a p4p NT-augmented value to `Reading`."""
    kind = _classify_kind(value)
    payload = _unpack_value(value, kind)
    severity = int(getattr(value, "severity", 0))
    status = int(getattr(value, "status", 0))
    timestamp = float(getattr(value, "timestamp", 0.0))
    sampled_at = datetime.fromtimestamp(timestamp, tz=UTC)
    return Reading(
        value=payload,
        kind=kind,
        quality=_quality_for(severity),
        sampled_at=sampled_at,
        quality_detail=_quality_detail_for(severity, status),
    )


class EpicsPvaControlPort:
    """p4p-backed `ControlPort` implementation. Production PVA client.

    See module docstring for the connection model + ACL table.
    """

    def __init__(self, *, default_timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._default_timeout_s = default_timeout_s
        self._context: Context | None = None
        self._closed = False

    def _ensure_context(self) -> Context:
        if self._context is None:
            self._context = Context(provider="pva")
        return self._context

    async def read(self, address: str) -> Reading:
        ctx = self._ensure_context()
        try:
            value = await asyncio.wait_for(
                ctx.get(address, request=_FIELD_REQUEST),
                timeout=self._default_timeout_s,
            )
        except (TimeoutError, Disconnected) as exc:
            raise ControlNotConnectedError(address) from exc
        except RemoteError as exc:
            raise ControlWriteRejectedError(address, str(exc)) from exc
        return _to_reading(value)

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
        ctx = self._ensure_context()
        try:
            await asyncio.wait_for(
                ctx.put(address, value, wait=wait),
                timeout=timeout_s,
            )
        except TimeoutError as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlTimeoutError.__name__,
            )
            raise ControlTimeoutError(address, timeout_s) from exc
        except Disconnected as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlNotConnectedError.__name__,
            )
            raise ControlNotConnectedError(address) from exc
        except RemoteError as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlWriteRejectedError.__name__,
            )
            raise ControlWriteRejectedError(address, str(exc)) from exc
        except ValueError as exc:
            _log.info(
                _DISPATCH_FAILED_EVENT,
                address=address,
                operation="write",
                correlation_id=str(correlation_id) if correlation_id is not None else None,
                status="failed",
                error_class=ControlValueCoercionError.__name__,
            )
            raise ControlValueCoercionError(
                address, raw_type=type(value).__name__, target_kind="pva put"
            ) from exc
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
        iterator's `aclose()`; same pattern as the other adapters.
        Setup (`_ensure_context` + `ctx.monitor`) runs on the
        generator's first `__anext__`.
        """
        return self._drain(address)

    async def _drain(self, address: str) -> AsyncGenerator[Reading]:
        ctx = self._ensure_context()
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def _callback(update: Any) -> None:
            # `put_nowait` keeps the callback synchronous (no yield to
            # scheduler) so two rapidly-arriving p4p updates preserve
            # FIFO order on the queue. `asyncio.Queue` is unbounded so
            # `put_nowait` never raises QueueFull.
            queue.put_nowait(update)

        sub = ctx.monitor(
            address,
            _callback,
            request=_FIELD_REQUEST,
            notify_disconnect=True,
        )
        seen_value = False
        try:
            while True:
                update = await queue.get()
                if isinstance(update, Disconnected):
                    if seen_value:
                        # Mid-stream disconnect: surface to caller so
                        # the consumer can decide to re-subscribe.
                        raise ControlNotConnectedError(address)
                    # Initial-state disconnect notification fires
                    # before p4p completes channel discovery; ignore
                    # and wait for the first value that follows.
                    continue
                if isinstance(update, RemoteError):
                    raise ControlWriteRejectedError(address, str(update))
                if isinstance(update, Exception):
                    raise ControlNotConnectedError(address) from update
                seen_value = True
                yield _to_reading(update)
        finally:
            with contextlib.suppress(Exception):
                sub.close()
            with contextlib.suppress(Exception):
                await sub.wait_closed()

    async def aclose(self) -> None:
        """Close the underlying p4p Context and drop adapter state.

        Idempotent. Unlike aioca, p4p's per-instance Context is the
        only state to clean up: there is no process-global broadcaster,
        so no `purge_channel_caches` analog at the fixture layer.
        """
        if self._closed:
            return
        self._closed = True
        if self._context is not None:
            with contextlib.suppress(Exception):
                self._context.close()
            self._context = None


__all__ = ["EpicsPvaControlPort"]
