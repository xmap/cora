"""Composition-root bridge: drive the Supply status observer from BLEPS PVs.

The Supply BC's `SupplyObserver` port is BC-local (`cora.supply.ports`)
and the `ControlPort` value-IO it needs is Operation-BC-owned
(`cora.operation.ports`). tach forbids `cora.supply -> cora.operation`,
so the bridging adapter lives here at the composition root, exactly as
`_enclosure_permit_observer` does. If a third cross-BC `ControlPort`
consumer appears, the rule-of-three move is to hoist `ControlPort` to
`cora.infrastructure.ports` and relocate both adapters into their BCs.

## Many channels, one Supply

Unlike the enclosure permit observer (one PV per Enclosure), a Supply
here is fed by many channels: eight cooling-water circuits behind
`2-BM cooling water`, and seven vacuum sections plus four valves behind
`2-BM beamline vacuum`. The Supply's status is the aggregate, and the
channel that caused it travels in the reason. That is what makes one
Supply per resource sufficient instead of one per circuit.

## Two axes, not three severities

BLEPS sorts channels into warnings, trips and faults, and those are not
one scale (see `docs/deployments/2-bm/operations.md`). This adapter
implements the two axes:

  - **process** (`trip`): the measured value crossed its limit, or a
    valve disobeyed. Drives status.
  - **trust** (`fault`): the reading is not believable. An off-scale
    reading pointing away from danger is physically implausible, so
    BLEPS reports it as a broken instrument. Drives nothing; it removes
    that channel from the aggregate.

`Communications_Fault` is the trust axis for the whole system: while it
stands, or while its own PV cannot be read, no observation is emitted at
all.

Warnings are deliberately NOT wired. See the module note below.

## Edges, not levels

`Recovering` is emitted only on the tripped-to-clear edge, never as a
level, because `Recovering` is reachable only from `Unavailable`: a
healthy Supply re-observed as clear would be a rejected transition on
every tick. So this adapter tracks per-Supply whether it has an
outstanding trip and speaks only when that changes. A first reading that
is already clear says nothing at all, since "nothing is wrong" is not a
fact a monitor needs to assert about a Supply that is already Available.

`Available` is never emitted. The furthest a monitor goes is
`Recovering`; a person closes the loop with `restore_supply`.

## Knowing nothing is not the same as knowing it is fine

If every channel behind a Supply is excluded (each one's instrument
faulted, or the whole system's comms faulted), the adapter emits
nothing. It does NOT read "no trips among the channels I trust" as clear
when it trusts none of them. That distinction is the whole reason the
trust axis is separate from the process axis.

## Warnings are not wired, and why

The 30 warning channels would map to `Degraded`, but `Degraded` is a
one-way door in the shipped Supply FSM: the `SupplyStatus` docstring
lists `Degraded -> Available`, yet no slice implements it
(`mark_supply_available` accepts only `Unknown`, `restore_supply` only
`Recovering`), so a Supply driven to `Degraded` can only go deeper. A
latched BLEPS warning that nobody resets would park a resource in a
state an operator cannot leave without first declaring it Unavailable.
Wiring warnings therefore waits on that gap being closed deliberately;
until then this adapter carries trips only, and the omission is visible
here rather than silent.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.operation.ports.control_port import ControlNotConnectedError, Measurement
from cora.supply.ports.supply_observer import SupplyObservation, SupplyObserverScope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence

    from cora.infrastructure.ports import Clock
    from cora.operation.ports.control_port import ControlPort

_SOURCE_KIND = "EpicsPv"
_UNAVAILABLE = "Unavailable"
_RECOVERING = "Recovering"


@dataclass(frozen=True)
class BlepsChannel:
    """One BLEPS channel feeding one Supply.

    `supply_code` is the Supply this channel contributes to.

    `label` is the operator-facing channel name that lands in the
    transition reason ("Flow2 (M1 and DMM circuit)"). This is where the
    per-circuit detail survives: the status says a run cannot draw on the
    resource, the label says which of the eight said so.

    `trip_pv` is the process-axis PV: a flow below set point, a vacuum
    section tripped, a valve faulted. Non-zero means tripped.

    `fault_pv` is the optional trust-axis PV: the instrumentation fault
    for this same channel (`Flow2.Over_Range_Fault`). Non-zero means this
    channel's `trip_pv` cannot be believed and the channel drops out of
    the aggregate. Valves and vacuum sections have no separate
    instrumentation fault, so this is `None` for them.
    """

    supply_code: str
    label: str
    trip_pv: str
    fault_pv: str | None = None


def is_asserted(reading: Measurement) -> bool | None:
    """Is this BLEPS flag high? `None` when the reading cannot be believed.

    BLEPS flags are binary. A non-Good quality reading, or a value that
    is not an integer, is not a low reading: it is an unknown one, and
    conflating the two would let a dead PV read as "no fault here".
    """
    if reading.quality != "Good":
        return None
    try:
        return int(reading.value) != 0
    except (TypeError, ValueError):
        return None


class _PumpDone:
    """Per-PV sentinel pushed onto the merge queue when a pump exits."""

    __slots__ = ()


_PUMP_DONE = _PumpDone()


class ControlPortBlepsSupplyObserver:
    """`SupplyObserver` over a `ControlPort`, aggregating BLEPS channels."""

    def __init__(
        self,
        *,
        control_port: ControlPort,
        channels: Sequence[BlepsChannel],
        comms_fault_pv: str | None,
        clock: Clock,
    ) -> None:
        self._control_port = control_port
        self._channels = tuple(channels)
        self._comms_fault_pv = comms_fault_pv
        self._clock = clock

    def observe(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        return self._drain(scope)

    async def _drain(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        channels = [c for c in self._channels if c.supply_code in scope.supply_codes]
        if not channels:
            return

        pvs = self._subscribed_pvs(channels)
        # Latest believed value per PV. Absent means never read; None
        # means read but not believable. Both are "unknown", and neither
        # is "low".
        latest: dict[str, bool | None] = {}
        tripped: dict[str, bool] = {}

        queue: asyncio.Queue[tuple[str, bool | None] | _PumpDone] = asyncio.Queue()
        tasks = [asyncio.create_task(self._pump(pv, queue)) for pv in pvs]
        remaining = len(tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if isinstance(item, _PumpDone):
                    remaining -= 1
                    continue
                pv, value = item
                latest[pv] = value
                for observation in self._reconcile(channels, latest, tripped):
                    yield observation
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _subscribed_pvs(self, channels: Iterable[BlepsChannel]) -> list[str]:
        """Subscription order: trust before process, system before channel.

        The comms flag comes first, then each channel's instrumentation
        fault ahead of its trip. Order does not matter at steady state,
        when every PV holds a live value, but it decides what the
        aggregate can conclude while the picture is still filling in.
        Establishing whether a channel is believable before reading what
        it says means the first complete verdict is a real one, rather
        than a trip arriving against an unknown trust flag and being
        discarded.
        """
        pvs: list[str] = []
        if self._comms_fault_pv:
            pvs.append(self._comms_fault_pv)
        for channel in channels:
            if channel.fault_pv:
                pvs.append(channel.fault_pv)
            pvs.append(channel.trip_pv)
        # Dedupe, preserving that order.
        return list(dict.fromkeys(pvs))

    def _reconcile(
        self,
        channels: Sequence[BlepsChannel],
        latest: Mapping[str, bool | None],
        tripped: dict[str, bool],
    ) -> list[SupplyObservation]:
        """Recompute every Supply's aggregate; emit only on edges."""
        if self._comms_lost(latest):
            return []
        observations: list[SupplyObservation] = []
        for supply_code in sorted({c.supply_code for c in channels}):
            supply_channels = [c for c in channels if c.supply_code == supply_code]
            verdict = self._aggregate(supply_channels, latest)
            if verdict is None:
                continue
            now_tripped, culprits = verdict
            was_tripped = tripped.get(supply_code)
            if was_tripped == now_tripped:
                continue
            if now_tripped:
                tripped[supply_code] = True
                observations.append(
                    self._observation(
                        supply_code,
                        _UNAVAILABLE,
                        reason=f"BLEPS trip: {', '.join(culprits)}",
                        pv=supply_channels[0].trip_pv,
                    )
                )
            elif was_tripped is None:
                # First believable reading and nothing is wrong: record
                # that we are watching, do not assert anything.
                tripped[supply_code] = False
            else:
                tripped[supply_code] = False
                observations.append(
                    self._observation(
                        supply_code,
                        _RECOVERING,
                        reason="BLEPS trips cleared; awaiting operator confirmation",
                        pv=supply_channels[0].trip_pv,
                    )
                )
        return observations

    def _comms_lost(self, latest: Mapping[str, bool | None]) -> bool:
        """Is the whole BLEPS reading untrustworthy right now?

        True when the comms-fault flag is asserted, and also when it is
        configured but not yet believably read: a comms flag we cannot
        read is precisely the condition it exists to report.
        """
        if not self._comms_fault_pv:
            return False
        return latest.get(self._comms_fault_pv) is not False

    def _aggregate(
        self, channels: Sequence[BlepsChannel], latest: Mapping[str, bool | None]
    ) -> tuple[bool, tuple[str, ...]] | None:
        """Fold trusted channels into (is_tripped, culprit labels).

        `None` when nothing can be concluded: no channel behind this
        Supply has a believable trip reading, because each is either
        unread or instrument-faulted. Knowing nothing is not knowing it
        is fine.
        """
        trusted = 0
        culprits: list[str] = []
        for channel in channels:
            if channel.fault_pv and latest.get(channel.fault_pv) is not False:
                continue  # instrument faulted, or its fault flag unread
            trip = latest.get(channel.trip_pv)
            if trip is None:
                continue  # unread, or read but not believable
            trusted += 1
            if trip:
                culprits.append(channel.label)
        if trusted == 0:
            return None
        return bool(culprits), tuple(culprits)

    def _observation(
        self, supply_code: str, status: str, *, reason: str, pv: str
    ) -> SupplyObservation:
        return SupplyObservation(
            supply_code=supply_code,
            observed_status=status,
            observed_at=self._clock.now(),
            reason=reason,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    async def _pump(
        self, pv: str, queue: asyncio.Queue[tuple[str, bool | None] | _PumpDone]
    ) -> None:
        """Forward one PV's believability to the merge queue.

        A clean stream end keeps the last reading rather than voiding it,
        which is where this differs from `_enclosure_permit_observer`. A
        clean end means no further updates, not that the last value was
        wrong, and voiding it here would be actively harmful: a Supply's
        verdict needs several PVs believable at once, so discarding a
        good reading the moment its stream closed would leave the
        aggregate permanently unable to conclude.

        Genuine loss still voids the reading: `ControlNotConnectedError`
        is the port's contract for a dropped subscription, and an
        unbelievable channel drops out of the aggregate, which leaves the
        Supply's status standing at whatever was last written rather than
        being overwritten by a guess.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                queue.put_nowait((pv, is_asserted(reading)))
        except ControlNotConnectedError:
            queue.put_nowait((pv, None))
        finally:
            queue.put_nowait(_PUMP_DONE)


__all__ = ["BlepsChannel", "ControlPortBlepsSupplyObserver", "is_asserted"]
