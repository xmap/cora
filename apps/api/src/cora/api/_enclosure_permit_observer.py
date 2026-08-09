"""Composition-root bridge: drive the Enclosure permit observer from ControlPort.

The Enclosure BC's `EnclosureObserver` port is BC-local
(`cora.enclosure.ports`) and the `ControlPort` value-IO it needs is
Operation-BC-owned (`cora.operation.ports`). tach forbids
`cora.enclosure -> cora.operation`, so the adapter that bridges the two
lives here at the composition root: `cora.api` is the one module that
depends on both BCs. If a third cross-BC `ControlPort` consumer appears,
the rule-of-three move is to hoist `ControlPort` to
`cora.infrastructure.ports` and relocate this adapter into
`cora.enclosure.adapters`.

Maps each configured enclosure's SecureM PV to an `EnclosureObservation`:
`SecureM == 1 -> Permitted`, `== 0 -> NotPermitted`, `Bad` quality or
any other value -> `Unknown`. A PV disconnect (or a clean stream end)
emits one `Unknown` observation so a dead permit signal fails the run
gate closed rather than leaving a stale `Permitted`.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
)
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping
    from datetime import datetime

    from cora.infrastructure.ports import Clock
    from cora.operation.ports.control_port import ControlPort

_SOURCE_KIND = "EpicsPv"
_PERMITTED = "Permitted"
_NOT_PERMITTED = "NotPermitted"
_UNKNOWN = "Unknown"

# Conventional EPICS binary state labels. A DBR_ENUM reading reaches
# this module as its resolved label, never as its index, so the label
# is the only thing left to compare against.
_PERMITTED_LABELS = frozenset({"1", "ON", "TRUE", "YES"})
_NOT_PERMITTED_LABELS = frozenset({"0", "OFF", "FALSE", "NO"})


def permit_status_from_reading(reading: Measurement) -> str:
    """Map a SecureM `Measurement` to an Enclosure permit-status string.

    SecureM polarity: `1` = searched / secured -> `Permitted`; `0` ->
    `NotPermitted`. A `Bad`-quality reading, or any value this cannot
    resolve to 0 / 1, flattens to `Unknown` (the conservative,
    gate-fails-closed status).

    The quality floor here is `Bad`, not `Good`, and that is a
    deliberate choice for this consumer. A permit signal is one of the
    values a facility most often annotates with a designed alarm:
    2-BM's `S02BM-PSS:StaB:SecureM` sits at MAJOR whenever the hutch is
    not secured, which is most of the time, so an `== "Good"` floor
    made a hutch CORA could plainly read report `Unknown` forever. The
    question this consumer asks is "can I believe this value", not "can
    I act on it", and only `Bad` says the value is not believable. See
    `epics_ca_control_port._SEVERITY_TO_QUALITY`.

    The loosening is one-directional and worth naming: an alarmed
    reading of `0` still closes the gate, while an alarmed reading of
    `1` now opens it where it previously did not. That is acceptable
    because CORA's permit status records what the interlock reports and
    actuates nothing; the PSS, not CORA, is what holds the hutch.

    Both shapes a CA adapter can hand back are accepted, because a
    real SecureM is a `bi` record and arrives as `kind="Categorical"`.
    For DBR_ENUM, `EpicsCaControlPort` resolves the index to its label
    and the index is no longer on the reading, so the label is all
    there is to read. `ON` / `OFF` are the stock EPICS ZNAM / ONAM
    defaults; `TRUE` / `FALSE` and `YES` / `NO` are the other
    conventional binary pairs. A facility that renames its states
    resolves to `Unknown`, which fails the gate closed and surfaces as
    a seam question rather than as a wrong permit.

    Read against 2-BM on 2026-08-09, where `S02BM-PSS:StaA:SecureM`
    reads `'ON'`: the previous numeric-only form raised on `int('ON')`
    and reported a correctly secured hutch as `Unknown`.
    """
    if reading.quality == "Bad":
        return _UNKNOWN
    code = _binary_code(reading.value)
    if code == 1:
        return _PERMITTED
    if code == 0:
        return _NOT_PERMITTED
    return _UNKNOWN


def _binary_code(value: object) -> int | None:
    """Resolve a SecureM reading to 1 / 0, or None when it is neither."""
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _PERMITTED_LABELS:
            return 1
        if token in _NOT_PERMITTED_LABELS:
            return 0
        return None
    try:
        code = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return code if code in (0, 1) else None


class _PumpDone:
    """Per-PV sentinel pushed onto the merge queue when a pump exits."""

    __slots__ = ()


_PUMP_DONE = _PumpDone()


class ControlPortEnclosureObserver:
    """`EnclosureObserver` over a `ControlPort` (one SecureM PV per enclosure)."""

    def __init__(
        self,
        *,
        control_port: ControlPort,
        permit_pvs: Mapping[str, str],
        clock: Clock,
    ) -> None:
        self._control_port = control_port
        self._permit_pvs = dict(permit_pvs)
        self._clock = clock

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        pvs = [
            (code, self._permit_pvs[code])
            for code in sorted(scope.enclosure_codes)
            if code in self._permit_pvs
        ]
        if not pvs:
            return
        queue: asyncio.Queue[EnclosureObservation | _PumpDone] = asyncio.Queue()
        tasks = [asyncio.create_task(self._pump(code, pv, queue)) for code, pv in pvs]
        remaining = len(tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if isinstance(item, _PumpDone):
                    remaining -= 1
                    continue
                yield item
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _pump(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[EnclosureObservation | _PumpDone],
    ) -> None:
        try:
            async for reading in self._control_port.subscribe(pv):
                queue.put_nowait(
                    self._observation(
                        code, pv, permit_status_from_reading(reading), reading.produced_at
                    )
                )
            # Clean stream end: permit becomes Unknown until re-subscribed.
            queue.put_nowait(self._unknown(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unknown(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    def _observation(
        self, code: str, pv: str, status: str, observed_at: datetime | None
    ) -> EnclosureObservation:
        return EnclosureObservation(
            enclosure_code=code,
            observed_status=status,
            observed_at=observed_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _unknown(self, code: str, pv: str) -> EnclosureObservation:
        return self._observation(code, pv, _UNKNOWN, self._clock.now())


__all__ = ["ControlPortEnclosureObserver", "permit_status_from_reading"]
