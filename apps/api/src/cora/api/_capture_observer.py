"""Composition-root bridge: drive the capture observer from ControlPort.

The Run BC's `CaptureObserver` port is BC-local (`cora.run.ports`) and
the `ControlPort` value-IO it needs is Operation-BC-owned
(`cora.operation.ports`). tach forbids `cora.run -> cora.operation`, so
the adapter that bridges the two lives here at the composition root,
mirroring `_enclosure_permit_observer.py` exactly. If a third cross-BC
`ControlPort` consumer appears, the rule-of-three move is to hoist
`ControlPort` to `cora.infrastructure.ports`.

Maps each configured capture code's `status` PV to a
`CaptureLifecycleObservation` by looking its decoded text up in the
deployment's declared `capture_status_phases` table
(`classify_capture_status`); a literal absent from the table
classifies `UNRECOGNIZED` rather than being dropped or coerced into a
nearby phase. The optional `abort` role layers a direct `ABORTED`
claim on top (slice 9); the optional `images_saved` /
`images_collected` progress roles (slice 10) each pump their own
`CaptureProgressObservation` onto the same merged stream, siblings of
the phase pumps.

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
`CaptureLifecycleObservation`'s own port-level contract for the
probe-only case. A progress pump has no `_unreached` counterpart at
all: `CaptureProgressObservation.value` is a required float with no
"no claim" shape, so its disconnect / clean-end simply stops the pump
rather than fabricating a reading (see `_pump_progress`).

## The bug that would have shipped without checking the real PV, again

Slice 9 caught 2-BM's `AbortScan` resolving to the ENUM label `'No'`,
not `0`. Slice 10 caught the same class of trap on `ImagesSaved` /
`ImagesCollected`: they are `stringout` records at 2-BM, and TomoScan
writes `"<done>/<total>"` onto them (`update_status()` in the upstream
`decarlof/tomoscan` source), never a bare number. `_finite_float`'s
first cut assumed a plain float; every real reading would have failed
to parse and the feature would have shipped recording nothing on the
real beamline, with no error anywhere; a deployment can watch a whole
scan complete and never notice the record stayed empty. Caught by
checking the upstream source's own write path rather than trusting the
`Settings.capture_watch_pvs` docstring's example. `_finite_float` now
accepts both shapes and keeps only the numerator; see that function's
own docstring for why the denominator is deliberately discarded, not
lost.

## Permit probe trail's sibling-poller shape, reused unchanged

Same reasoning as the Enclosure adapter: `_poll` is a SIBLING of
`_pump`, not nested inside it, because `_pump` returns as soon as its
subscription ends and `_drain` only re-subscribes after every pump has
returned; a poller living inside `_pump` would die with it and could
never observe the PV's recovery.
"""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING

from cora.operation.ports.control_port import ControlNotConnectedError
from cora.run.ports.capture_observer import (
    AnyCaptureObservation,
    CaptureLifecycleObservation,
    CaptureObserverScope,
    CapturePhase,
    CaptureProgressObservation,
)
from cora.shared.reach import ReachTier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.operation.ports.control_port import ControlPort, Measurement

_SOURCE_KIND = "EpicsPv"
_STATUS_ROLE = "status"
_ABORT_ROLE = "abort"
_PROGRESS_ROLES = ("images_saved", "images_collected")
"""CORA-owned progress role keys, matching `Settings.capture_watch_pvs`'s
documented example. `server_running` stays declared-and-unread: tool
liveness is a different concern from capture progress (slice 10)."""

# Conventional EPICS binary state labels, mirroring
# `_enclosure_permit_observer._PERMITTED_LABELS` / `_NOT_PERMITTED_LABELS`
# exactly: a DBR_ENUM reading through `EpicsCaControlPort` reaches this
# module as its resolved label, never as its index (2-BM's `AbortScan`
# is confirmed live as one such ENUM, resolving to `'No'`), so the label
# is the only thing left to compare against. `CaprotoControlPort`, by
# contrast, leaves the raw integer unresolved; the `int(value)` fallback
# below covers that shape too.
_ASSERTED_LABELS = frozenset({"1", "ON", "TRUE", "YES"})
_CLEAR_LABELS = frozenset({"0", "OFF", "FALSE", "NO"})


def _binary_code(value: object) -> int | None:
    """Resolve a binary-role reading to 1 / 0, or None when it is neither.

    Unrecognized resolves to `None`, never a guess: same fail-toward-
    silence posture as `_enclosure_permit_observer._binary_code`, whose
    docstring documents the production incident (`int('ON')` raising)
    that made string-label matching necessary in the first place.
    """
    if isinstance(value, str):
        token = value.strip().upper()
        if token in _ASSERTED_LABELS:
            return 1
        if token in _CLEAR_LABELS:
            return 0
        return None
    try:
        code = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return code if code in (0, 1) else None


def _finite_float(value: object) -> float | None:
    """Coerce a progress-role reading to a finite float, or `None`.

    Two accepted shapes: a bare number, and 2-BM's REAL format, a
    `"<done>/<total>"` string. `ImagesSaved` / `ImagesCollected` are
    `stringout` records at 2-BM (not numeric ones): TomoScan's
    `update_status()` writes `f"{num_saved}/{num_to_save}"` /
    `f"{num_collected}/{num_images}"` onto them, confirmed against the
    upstream `decarlof/tomoscan` source, `tomoScan.template` (both
    declared `record(stringout, ...)`) and `tomoscan.py`'s
    `update_status`. A bare-number reading enqueues the number
    unchanged, for a future substrate or role that IS numeric.

    Only the numerator is kept: `images_saved`'s value is "how many
    images have actually been saved", the count left of the slash. The
    denominator (the commanded total) is a distinct fact -- the
    intended scan length, not a progress count -- and is deliberately
    NOT carried onto this channel; a consumer that needs it reads the
    Plan's own parameters instead. This is a decision, not an
    oversight: see this module's docstring.

    Fail-toward-silence, mirroring `_binary_code`: a reading that is
    neither shape, or resolves to NaN/Infinity, enqueues nothing
    rather than reaching `append_observations`, which raises
    `InvalidObservationValueError` on NaN/Inf and would fail an entire
    batch over one bad reading.
    """
    numerator: object = value
    if isinstance(value, str) and "/" in value:
        numerator, _, _total = value.partition("/")
    try:
        result = float(numerator)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


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
    """`CaptureObserver` over a `ControlPort` (`status` + optional `abort` +
    optional progress PVs per capture code).

    `capture_pvs` is code -> role -> PV, matching
    `Settings.capture_watch_pvs`. The `status` role is required; a code
    whose PV set has no `status` entry cannot be watched and is
    silently excluded from scope, mirroring the Enclosure adapter's
    `if code in self._permit_pvs` filter. The `abort` role is optional
    per code: when declared, a truthy reading on it is a direct
    `ABORTED` phase claim, letting a real abort be distinguished from a
    successful end even where the `status` PV alone cannot (2-BM's
    `fly_scan` writes the identical `'Scan complete'` literal on both).
    A code with no `abort` entry watches `status` only, exactly as
    before this role existed. The `images_saved` / `images_collected`
    progress roles (also optional, independently declared per code)
    each pump `CaptureProgressObservation` readings; `server_running`
    stays declared and unread (tool liveness, not capture progress).
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
        self._abort_pvs = {
            code: roles[_ABORT_ROLE] for code, roles in capture_pvs.items() if _ABORT_ROLE in roles
        }
        self._progress_pvs = {
            code: filtered
            for code, roles in capture_pvs.items()
            if (filtered := {role: pv for role, pv in roles.items() if role in _PROGRESS_ROLES})
        }
        self._status_phases = dict(status_phases)
        self._tick_seconds = tick_seconds

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        return self._drain(scope)

    async def _drain(self, scope: CaptureObserverScope) -> AsyncGenerator[AnyCaptureObservation]:
        pvs = [
            (code, self._status_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._status_pvs
        ]
        if not pvs:
            return
        abort_pvs = [
            (code, self._abort_pvs[code])
            for code in sorted(scope.capture_codes)
            if code in self._abort_pvs
        ]
        progress_pvs = [
            (code, role, pv)
            for code in sorted(scope.capture_codes)
            if code in self._progress_pvs
            for role, pv in sorted(self._progress_pvs[code].items())
        ]
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone] = asyncio.Queue()
        pump_tasks = (
            [asyncio.create_task(self._pump(code, pv, queue)) for code, pv in pvs]
            + [asyncio.create_task(self._pump_abort(code, pv, queue)) for code, pv in abort_pvs]
            + [
                asyncio.create_task(self._pump_progress(code, role, pv, queue))
                for code, role, pv in progress_pvs
            ]
        )
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
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
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

    async def _pump_abort(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for the optional `abort` role.

        Unlike `_pump`, not every reading is enqueued: a falsy value (the
        busy record's idle/reset state) makes no phase claim at all and
        must not be pushed as a no-op observation, per `_from_abort_reading`.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_abort_reading(code, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
            queue.put_nowait(self._unreached(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unreached(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _pump_progress(
        self,
        code: str,
        role: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
    ) -> None:
        """Sibling pump for an optional progress role (`images_saved`,
        `images_collected`).

        No `_unreached` counterpart: `CaptureProgressObservation.value`
        is a required float with no "no claim" shape (unlike
        `CaptureLifecycleObservation.phase`, which can legitimately be
        `None`), so a disconnect or clean stream end here simply stops
        the pump rather than fabricating a reading.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                observation = self._from_progress_reading(code, role, pv, reading)
                if observation is not None:
                    queue.put_nowait(observation)
        except ControlNotConnectedError:
            pass
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _poll(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[AnyCaptureObservation | _PumpDone],
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

    def _from_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CaptureLifecycleObservation:
        reported_status = str(reading.value)
        phase = classify_capture_status(reported_status, self._status_phases)
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=reported_status,
            phase=phase,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_abort_reading(
        self, code: str, pv: str, reading: Measurement
    ) -> CaptureLifecycleObservation | None:
        """An asserted abort-role reading is a direct `ABORTED` claim.

        NOT Python truthiness: 2-BM's `AbortScan` is a DBR_ENUM that
        resolves to the label `'No'` when idle, and `bool('No')` is
        `True`. `_binary_code` decodes the conventional EPICS binary
        labels (or a raw 0/1 index) instead, so "No" correctly resolves
        to clear, not asserted.

        A clear or unresolvable reading makes no phase claim: it is not
        "the capture is not aborted" so much as "nothing happened on
        this PV" (or a label this cannot decode), and reporting it as a
        phase would let a stale idle read silently arrive between a
        real `Begun` and its `status` transitions. `None` return means
        the caller enqueues nothing.
        """
        if _binary_code(reading.value) != 1:
            return None
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=str(reading.value),
            phase=CapturePhase.ABORTED,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _from_progress_reading(
        self, code: str, role: str, pv: str, reading: Measurement
    ) -> CaptureProgressObservation | None:
        """A progress-role reading, decoded to a finite float.

        `None` return (no coercible finite value) means the caller
        enqueues nothing, matching `_from_abort_reading`'s fail-toward-
        silence posture: a garbled or non-numeric reading is dropped,
        never guessed at.
        """
        value = _finite_float(reading.value)
        if value is None:
            return None
        return CaptureProgressObservation(
            capture_code=code,
            role=role,
            value=value,
            reach_tier=ReachTier.RELAYED,
            observed_at=reading.produced_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _probe_only(self, code: str, pv: str, reach_tier: ReachTier) -> CaptureLifecycleObservation:
        """A poll tick's result: reach evidence with no status claim."""
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=reach_tier,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _unreached(self, code: str, pv: str) -> CaptureLifecycleObservation:
        """A disconnect or clean stream end: no status claim, no phase.

        See this module's docstring, "One deliberate inversion from the
        Enclosure precedent", for why this must not synthesize a phase.
        """
        return CaptureLifecycleObservation(
            capture_code=code,
            reported_status=None,
            phase=None,
            reach_tier=ReachTier.UNREACHED,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )


__all__ = ["ControlPortCaptureObserver", "classify_capture_status"]
