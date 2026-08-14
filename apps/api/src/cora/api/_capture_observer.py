"""Composition-root bridge: drive the capture observer from ControlPort.

The Run BC's `CaptureObserver` port is BC-local (`cora.run.ports`) and
the `ControlPort` value-IO it needs is Operation-BC-owned
(`cora.operation.ports`). tach forbids `cora.run -> cora.operation`, so
the adapter that bridges the two lives here at the composition root,
mirroring `_enclosure_permit_observer.py` exactly. If a third cross-BC
`ControlPort` consumer appears, the rule-of-three move is to hoist
`ControlPort` to `cora.infrastructure.ports`.

Maps each configured capture code's `status` PV to a `CaptureObservation`
by looking its decoded text up in the deployment's declared
`capture_status_phases` table (`classify_capture_status`); a literal
absent from the table classifies `UNRECOGNIZED` rather than being
dropped or coerced into a nearby phase.

## One deliberate inversion from the Enclosure precedent

`ControlPortEnclosureObserver` synthesizes an `Unknown` STATUS CLAIM on
disconnect, because a dead permit signal must fail the run-start gate
closed rather than leave a stale `Permitted` standing. There is no such
gate here, and reading a disconnect as a real observation would
fabricate one: it would either assert a phase no substrate reading
backs, or, if mapped to `UNRECOGNIZED`, misrepresent a communication
failure as a vocabulary problem. So `_unreached` here carries NO status
claim at all (`reported_status=None`, `phase=None`), the same shape a
probe-only poll tick already uses, exactly mirroring
`CaptureObservation`'s own port-level contract for the probe-only case.

## Permit probe trail's sibling-poller shape, reused unchanged

Same reasoning as the Enclosure adapter: `_poll` is a SIBLING of
`_pump`, not nested inside it, because `_pump` returns as soon as its
subscription ends and `_drain` only re-subscribes after every pump has
returned; a poller living inside `_pump` would die with it and could
never observe the PV's recovery.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.operation.ports.control_port import ControlNotConnectedError
from cora.run.ports.capture_observer import CaptureObservation, CaptureObserverScope, CapturePhase
from cora.shared.reach import ReachTier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.operation.ports.control_port import ControlPort, Measurement

_SOURCE_KIND = "EpicsPv"
_STATUS_ROLE = "status"


def classify_capture_status(reported_status: str, status_phases: Mapping[str, str]) -> CapturePhase:
    """Classify a decoded status literal against the deployment's declared table.

    A literal absent from `status_phases` classifies as
    `CapturePhase.UNRECOGNIZED`. This also covers the Bad-quality-reading
    case with no special handling needed: an unresolvable or garbled
    string is exceedingly unlikely to match a declared literal, so it
    naturally falls to UNRECOGNIZED, which is the correct signal ("the
    substrate said something CORA cannot classify"), rather than a
    fabricated phase.
    """
    mapped = status_phases.get(reported_status)
    if mapped is None:
        return CapturePhase.UNRECOGNIZED
    return CapturePhase(mapped)


class _PumpDone:
    """Per-PV sentinel pushed onto the merge queue when a pump exits."""

    __slots__ = ()


_PUMP_DONE = _PumpDone()


class ControlPortCaptureObserver:
    """`CaptureObserver` over a `ControlPort` (one `status` PV per capture code).

    `capture_pvs` is code -> role -> PV, matching
    `Settings.capture_watch_pvs`. Only the `status` role is subscribed
    in this slice; a code whose PV set has no `status` entry cannot be
    watched and is silently excluded from scope, mirroring the
    Enclosure adapter's `if code in self._permit_pvs` filter. The other
    declared roles (`server_running`, `abort`, `images_saved`,
    `images_collected`) are read by a later slice; declaring them now
    costs nothing and lets a deployment's config stabilize ahead of the
    code that consumes it.
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        capture_pvs: Mapping[str, Mapping[str, str]],
        status_phases: Mapping[str, str],
        tick_seconds: float | None = None,
    ) -> None:
        self._control_port = control_port
        self._status_pvs = {
            code: roles[_STATUS_ROLE]
            for code, roles in capture_pvs.items()
            if _STATUS_ROLE in roles
        }
        self._status_phases = dict(status_phases)
        self._tick_seconds = tick_seconds

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        pvs = [
            (code, self._status_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._status_pvs
        ]
        if not pvs:
            return
        queue: asyncio.Queue[CaptureObservation | _PumpDone] = asyncio.Queue()
        pump_tasks = [asyncio.create_task(self._pump(code, pv, queue)) for code, pv in pvs]
        poll_tasks = (
            [asyncio.create_task(self._poll(code, pv, queue)) for code, pv in pvs]
            if self._tick_seconds is not None
            else []
        )
        tasks = pump_tasks + poll_tasks
        # Only pumps ever signal completion; a poller runs until the
        # `finally` below cancels it, so it must not hold this open.
        remaining = len(pump_tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if isinstance(item, _PumpDone):
                    remaining -= 1
                    continue
                yield item
            # Every pump has finished, but a still-running poller can have
            # enqueued a probe in the same instant the final _PumpDone was
            # read. Drain exactly what is ALREADY queued right now,
            # synchronously, into a list before yielding any of it: see
            # `ControlPortEnclosureObserver._drain` for the full reasoning.
            pending = queue.qsize()
            leftover = [queue.get_nowait() for _ in range(pending)]
            for item in leftover:
                if not isinstance(item, _PumpDone):
                    yield item
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _pump(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[CaptureObservation | _PumpDone],
    ) -> None:
        try:
            async for reading in self._control_port.subscribe(pv):
                queue.put_nowait(self._from_reading(code, pv, reading))
            # Clean stream end: no status claim, mirroring a disconnect.
            queue.put_nowait(self._unreached(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unreached(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _poll(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[CaptureObservation | _PumpDone],
    ) -> None:
        """Re-affirm reach to `pv` every `_tick_seconds`, independent of push.

        Never pushes `_PumpDone`: a sibling of `_pump`, not a stage in
        its lifecycle. See `ControlPortEnclosureObserver._poll`.
        """
        assert self._tick_seconds is not None
        while True:
            await asyncio.sleep(self._tick_seconds)
            try:
                await self._control_port.read(pv)
            except Exception:  # any read failure is a failed probe, not a bug
                queue.put_nowait(self._probe_only(code, pv, ReachTier.UNREACHED))
            else:
                queue.put_nowait(self._probe_only(code, pv, ReachTier.RELAYED))

    def _from_reading(self, code: str, pv: str, reading: Measurement) -> CaptureObservation:
        reported_status = str(reading.value)
        phase = classify_capture_status(reported_status, self._status_phases)
        return CaptureObservation(
            capture_code=code,
            reported_status=reported_status,
            phase=phase,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _probe_only(self, code: str, pv: str, reach_tier: ReachTier) -> CaptureObservation:
        """A poll tick's result: reach evidence with no status claim."""
        return CaptureObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=reach_tier,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _unreached(self, code: str, pv: str) -> CaptureObservation:
        """A disconnect or clean stream end: no status claim, no phase.

        See this module's docstring, "One deliberate inversion from the
        Enclosure precedent", for why this must not synthesize a phase.
        """
        return CaptureObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=ReachTier.UNREACHED,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )


__all__ = ["ControlPortCaptureObserver", "classify_capture_status"]
