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
`SecureM == 1 -> Permitted`, `== 0 -> NotPermitted`, non-Good quality or
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


def permit_status_from_reading(reading: Measurement) -> str:
    """Map a SecureM `Measurement` to an Enclosure permit-status string.

    SecureM polarity: `1` = searched / secured -> `Permitted`; `0` ->
    `NotPermitted`. Non-Good quality, or any value that is not 0 / 1,
    flattens to `Unknown` (the conservative, gate-fails-closed status).
    """
    if reading.quality != "Good":
        return _UNKNOWN
    try:
        value = int(reading.value)
    except (TypeError, ValueError):
        return _UNKNOWN
    if value == 1:
        return _PERMITTED
    if value == 0:
        return _NOT_PERMITTED
    return _UNKNOWN


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
        self, code: str, pv: str, status: str, observed_at: datetime
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
