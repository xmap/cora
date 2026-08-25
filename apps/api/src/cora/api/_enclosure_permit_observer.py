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
gate closed rather than leaving a stale `Permitted`. That synthesized
observation carries NO substrate time, because there was no substrate
reading behind it; see `_unknown`.

## Permit probe trail: a sibling poller, not an in-pump interleave

When `tick_seconds` is configured, each PV also gets a sibling polling
task (`_poll`) alongside its push subscription (`_pump`), both feeding
the same queue. The poll never carries a status claim
(`observed_status=None`): it exists only to re-affirm reach on a fixed
cadence, independent of push traffic, because EPICS CA monitors are
change-only and a quiet permit PV would otherwise leave a probe-trail
gap that is really coverage, not an outage. See
[[project_enclosure_permit_probe_design]].

The poller is a SIBLING of `_pump`, not nested inside it, deliberately:
`_pump` returns as soon as its subscription ends (clean end or
disconnect), and `_drain` only re-subscribes after every pump has
returned. A poller living inside `_pump` would die with it and could
never observe a PV's recovery. As a sibling it keeps polling through a
dead push path and its `UNREACHED` probes are the only signal left that
this specific PV, not the whole deployment, is unreachable.

Because the poll never carries a status, it cannot drive a permit
transition and cannot be confused for evidence stronger than it is: a
successful poll proves only that the configured channel answered this
tick, never that the underlying signal is current (see `ReachTier`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
    ReachTier,
)
from cora.operation.ports.control_port import ControlNotConnectedError, Measurement
from cora.shared.binary_signal import binary_code
from cora.shared.quality import believable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping
    from datetime import datetime

    from cora.operation.ports.control_port import ControlPort

_SOURCE_KIND = "EpicsPv"
_PERMITTED = "Permitted"
_NOT_PERMITTED = "NotPermitted"
_UNKNOWN = "Unknown"


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

    The floor also bears on the IOC-restart window, but it covers less
    of that than it first appears, so do not lean on it. A record that
    has never had a value assigned reports `STAT=UDF` with
    `SEVR=INVALID`, which arrives here as `Bad` and flattens to
    `Unknown`, closing the gate. A record that was GIVEN a value
    without ever processing does not: a `field(VAL, ...)` default at
    load, or an autosave restore at boot, clears `UDF` and leaves
    `SEVR=NO_ALARM`, so it arrives as `Good` while still carrying no
    substrate timestamp. Measured on a scratch IOC, base 7.0.8 with
    autosave R5-11, 2026-08; see `tomography/tomoscan#182`.

    Which group 2-BM's SecureM falls into is unconfirmed, so this floor
    is not a restart guard. The only signal separating a stamped
    reading from an unstamped one is `produced_at`, which this path
    carries as evidence and never gates on.

    Both shapes a CA adapter can hand back are accepted, because a
    real SecureM is a `bi` record and arrives as `kind="Categorical"`.
    For DBR_ENUM the reading carries both halves: the resolved label on
    `Measurement.value` and the index it was resolved from on
    `Measurement.ordinal`. `binary_code` reads the index first, so a
    facility that renames its states no longer costs CORA the permit:
    `ON` / `OFF` are the stock EPICS ZNAM / ONAM defaults and the
    label path still accepts them (plus `TRUE` / `FALSE`, `YES` / `NO`),
    but that path is now the fallback for a reading with no index rather
    than the only road in. A reading CORA can resolve by neither route
    still yields `Unknown`, which fails the gate closed and surfaces as
    a seam question rather than as a wrong permit.

    Read against 2-BM on 2026-08-09, where `S02BM-PSS:StaA:SecureM`
    reads `'ON'`: the previous numeric-only form raised on `int('ON')`
    and reported a correctly secured hutch as `Unknown`.
    """
    if not believable(reading.quality):
        return _UNKNOWN
    code = binary_code(reading.value, ordinal=reading.ordinal)
    if code == 1:
        return _PERMITTED
    if code == 0:
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
        tick_seconds: float | None = None,
    ) -> None:
        self._control_port = control_port
        self._permit_pvs = dict(permit_pvs)
        self._tick_seconds = tick_seconds

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
            # read (asyncio.Queue.put_nowait needs no await, so it is not
            # ordered against the `remaining` check above). Drain exactly
            # what is ALREADY queued right now, synchronously, into a list
            # before yielding any of it: yielding suspends this generator
            # and hands control back to a poller, which could otherwise
            # keep queue.empty() perpetually False and stop `_drain` from
            # ever returning to let the outer loop reconnect.
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
        queue: asyncio.Queue[EnclosureObservation | _PumpDone],
    ) -> None:
        try:
            async for reading in self._control_port.subscribe(pv):
                # RELAYED unconditionally: a delivered reading is push
                # contact regardless of its mapped status. A Bad-quality
                # reading still maps to "Unknown" but is NOT the same
                # fact as `_unknown`'s disconnect: the substrate spoke
                # and said its value could not be believed, which is
                # reach with an unbelievable value, not absence of reach.
                queue.put_nowait(
                    self._observation(
                        code,
                        pv,
                        permit_status_from_reading(reading),
                        reading.produced_at,
                        reach_tier=ReachTier.RELAYED,
                    )
                )
            # Clean stream end: permit becomes Unknown until re-subscribed.
            queue.put_nowait(self._unknown(code, pv))
        except ControlNotConnectedError:
            queue.put_nowait(self._unknown(code, pv))
        finally:
            queue.put_nowait(_PUMP_DONE)

    async def _poll(
        self,
        code: str,
        pv: str,
        queue: asyncio.Queue[EnclosureObservation | _PumpDone],
    ) -> None:
        """Re-affirm reach to `pv` every `_tick_seconds`, independent of push.

        Never pushes `_PumpDone`: this task is a sibling of `_pump`, not
        a stage in its lifecycle, and runs until `_drain`'s `finally`
        cancels it on teardown. It ticks unconditionally, regardless of
        how much push traffic `pv` is producing, which is simpler than
        gating on push quiescence and avoids the "a chatty PV is never
        polled" surprise a quiescence-gated poll would carry.

        A tick that fails (any exception but cancellation) writes an
        `UNREACHED` probe-only observation and keeps polling; it never
        raises out of this loop and never touches `_pump`'s subscription.
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

    def _observation(
        self,
        code: str,
        pv: str,
        status: str,
        observed_at: datetime | None,
        *,
        reach_tier: ReachTier,
    ) -> EnclosureObservation:
        return EnclosureObservation(
            enclosure_code=code,
            observed_status=status,
            reach_tier=reach_tier,
            observed_at=observed_at,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _probe_only(self, code: str, pv: str, reach_tier: ReachTier) -> EnclosureObservation:
        """A poll tick's result: reach evidence with no status claim."""
        return EnclosureObservation(
            enclosure_code=code,
            observed_status=None,
            reach_tier=reach_tier,
            observed_at=None,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _unknown(self, code: str, pv: str) -> EnclosureObservation:
        """A disconnect or stream end, which carries NO substrate time.

        This used to stamp `clock.now()`, which is a CORA time wearing a
        substrate label. The port forbids exactly that
        (`enclosure_observer.EnclosureObservation`: an adapter with no
        substrate time MUST answer None rather than supply its own
        clock), and it is the same defect removed from the caproto
        adapter, one layer up.

        It was harmless only while the seam discarded the field. It stops
        being harmless the moment that time reaches a payload, and the
        inversion at 2-BM would be total: both PSS PVs report an
        undefined stamp, so every REAL reading yields None while every
        synthesized disconnect would carry a real-looking time. The
        column would be populated precisely when the substrate said
        nothing.

        The recording side keeps its own clock: the event's `occurred_at`
        still says when CORA learned of the disconnect. `reach_tier` is
        `UNREACHED`: a disconnect carries a status claim (`Unknown`, so
        the run gate still fails closed) but is not reach evidence.
        """
        return self._observation(code, pv, _UNKNOWN, None, reach_tier=ReachTier.UNREACHED)


__all__ = ["ControlPortEnclosureObserver", "permit_status_from_reading"]
