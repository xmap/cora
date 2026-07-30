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
channel that caused it travels in the reason and in `monitor_ref`.

## Two axes, not three severities

BLEPS sorts channels into warnings, trips and faults, and those are not
one scale (see `docs/deployments/2-bm/operations.md`). This adapter
implements the two axes:

  - **process** (`trip`): the measured value crossed its limit, or a
    valve disobeyed. Drives status.
  - **trust** (`fault`): the reading is not believable. An off-scale
    reading pointing away from danger is physically implausible, so
    BLEPS reports it as a broken instrument. Drives nothing; it removes
    that channel from the verdict.

`Communications_Fault` is the trust axis for the whole system: while it
stands, or while its own PV cannot be believably read, no observation is
emitted at all.

Warnings are deliberately NOT wired. See the module note at the bottom.

## Clear requires ALL channels, tripped requires only one

The asymmetry is the safety property, and getting it wrong was a real
fail-open bug caught in gate review. A Supply is reported:

  - **tripped** when ANY believable channel trips, and
  - **clear** only when EVERY channel is believable AND clear.

Anything else withholds. The tempting version, "no trips among the
channels I trust", is wrong: if the one channel carrying a standing trip
loses its instrument (or its subscription, or its quality flag) while a
sibling still reads clear, that version concludes the trip cleared. It
did not. It became unobservable, and those are opposite facts. So losing
sight of any channel costs the Supply its ability to be called clear,
and a resource stays down until it can be seen to be up.

## Stateless: levels, not edges

The adapter holds no per-Supply memory. It recomputes the verdict on
every reading and emits it, and the runtime decides what it means
against the Supply's real status. An earlier version tracked edges here,
which produced three separate defects: a lost append was never re-sent
(the enclosure precedent is immune precisely because it emits levels), a
re-subscribe reset the memory and stranded a Supply at `Unavailable`,
and the memory disagreed with the aggregate whenever an operator moved
it by hand. The aggregate's own status is the only trustworthy record of
where a Supply is, and the runtime is where it is readable.

Emission is naturally sparse despite being level-based, because EPICS
monitors fire on change: a beamline with nothing happening produces no
readings after the initial connect.

`Available` is never emitted. The furthest a monitor goes is
`Recovering`, and `cora.supply._monitor` drops even that unless the
Supply is actually `Unavailable`; a person closes the loop with
`restore_supply`.

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

from cora.infrastructure.logging import get_logger
from cora.supply.ports.supply_observer import SupplyObservation, SupplyObserverScope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence

    from cora.infrastructure.ports import Clock
    from cora.operation.ports.control_port import ControlPort, Measurement

_SOURCE_KIND = "EpicsPv"
_UNAVAILABLE = "Unavailable"
_RECOVERING = "Recovering"

_log = get_logger(__name__)


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
    the verdict. Valves and vacuum sections have no separate
    instrumentation fault, so this is `None` for them.
    """

    supply_code: str
    label: str
    trip_pv: str
    fault_pv: str | None = None


def flag_state_from_reading(reading: Measurement) -> bool | None:
    """Is this BLEPS flag high? `None` when the reading cannot be believed.

    Named `<value>_from_reading` rather than `is_*` because the third
    answer is load-bearing: a non-Good quality reading, or a value this
    function cannot interpret, is not a LOW reading, and conflating the
    two would let a dead PV read as "no fault here".

    ## Enum-valued records are not interpreted, deliberately

    BLEPS flags are binary on the PLC side, but how they surface over
    Channel Access depends on the record type the IOC declares. A
    `longin` / `ai` arrives as a number and is read here. A `bi` / `mbbi`
    is `DBR_ENUM`, and `EpicsCaControlPort` resolves those to their
    FORMAT_CTRL label STRING (`"TRIP"`, `"OK"`), falling back to the
    stringified index when the label cache is cold.

    A numeric string parses. A label does not, and this function does NOT
    guess at label vocabularies: mapping `"TRIP"` and friends to True
    would be inventing a fact about an IOC nobody here has read. It
    returns `None`, the caller logs it loudly, and the record types are an
    open question for staff (`bleps.substitutions` defines them). Until
    that is answered, an enum-valued deployment observes nothing, and
    says so in the log rather than looking healthy.
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


class BlepsSupplyObserver:
    """`SupplyObserver` over a `ControlPort`, aggregating BLEPS channels.

    Named `<Tech><Port>` per the adapter convention, with `Bleps` as the
    technology rather than `ControlPort`: the transport could change to
    PVA or Tango without touching a line of this class, whereas every
    rule in it is BLEPS's. The sibling `ControlPortEnclosureObserver`
    names its transport because that adapter has no vendor semantics of
    its own.

    The `control_port` handed in SHOULD already be write-guarded; the
    composition root wraps it, because CORA never writes to the
    interlock and a structural guarantee beats a reviewed one.
    """

    def __init__(
        self,
        *,
        control_port: ControlPort,
        channels: Sequence[BlepsChannel],
        communications_fault_pv: str | None,
        clock: Clock,
    ) -> None:
        self._control_port = control_port
        self._channels = tuple(channels)
        self._communications_fault_pv = communications_fault_pv
        self._clock = clock
        # Log-only, NOT verdict state: suppresses a repeated "feed is
        # dark" warning. Losing it would cost a log line and nothing else.
        self._reported_dark = False

    def observe(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        return self._drain(scope)

    async def _drain(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        channels = [c for c in self._channels if c.supply_code in scope.supply_codes]
        if not channels:
            return

        pvs = self._subscribed_pvs(channels)
        # Latest believed value per PV. Absent means never read; None
        # means read but not believable. Both are "unknown", and neither
        # is "low". This is a read cache, not a verdict: it is rebuilt
        # from scratch on every re-subscribe and nothing is inferred from
        # its absence.
        latest: dict[str, bool | None] = {}

        queue: asyncio.Queue[tuple[str, bool | None] | _PumpDone] = asyncio.Queue()
        tasks = [asyncio.create_task(self._pump(pv, queue), name=f"bleps-pump:{pv}") for pv in pvs]
        remaining = len(tasks)
        try:
            while remaining > 0:
                item = await queue.get()
                if isinstance(item, _PumpDone):
                    remaining -= 1
                    continue
                pv, value = item
                latest[pv] = value
                for observation in self._observations(channels, latest):
                    yield observation
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _subscribed_pvs(self, channels: Iterable[BlepsChannel]) -> list[str]:
        """Subscription order: trust before process, system before channel.

        The comms flag comes first, then each channel's instrumentation
        fault ahead of its trip. Order does not change any verdict now
        that "clear" requires every channel, but it still decides how
        quickly the first real verdict can form.
        """
        pvs: list[str] = []
        if self._communications_fault_pv:
            pvs.append(self._communications_fault_pv)
        for channel in channels:
            if channel.fault_pv:
                pvs.append(channel.fault_pv)
            pvs.append(channel.trip_pv)
        # Dedupe, preserving that order.
        return list(dict.fromkeys(pvs))

    def _observations(
        self, channels: Sequence[BlepsChannel], latest: Mapping[str, bool | None]
    ) -> list[SupplyObservation]:
        """Recompute and report every Supply's verdict. Stateless."""
        if self._communications_lost(latest):
            return []
        observations: list[SupplyObservation] = []
        for supply_code in sorted({c.supply_code for c in channels}):
            supply_channels = [c for c in channels if c.supply_code == supply_code]
            verdict = self._verdict(supply_channels, latest)
            if verdict is None:
                continue
            culprits = verdict
            if culprits:
                observations.append(
                    self._observation(
                        supply_code,
                        _UNAVAILABLE,
                        reason=f"BLEPS trip: {', '.join(label for label, _ in culprits)}",
                        pv=culprits[0][1],
                    )
                )
            else:
                observations.append(
                    self._observation(
                        supply_code,
                        _RECOVERING,
                        reason="BLEPS trips clear; awaiting operator confirmation",
                        pv=supply_channels[0].trip_pv,
                    )
                )
        return observations

    def _communications_lost(self, latest: Mapping[str, bool | None]) -> bool:
        """Is the whole BLEPS reading untrustworthy right now?

        True when the comms-fault flag is asserted, and also when it is
        configured but not yet believably read: a comms flag we cannot
        read is precisely the condition it exists to report.

        Warns on the way into that state so a dark feed is visible.
        Without it, a typo'd comms PV and a healthy beamline are
        indistinguishable, both being total silence.
        """
        if not self._communications_fault_pv:
            return False
        lost = latest.get(self._communications_fault_pv) is not False
        if lost and not self._reported_dark:
            self._reported_dark = True
            _log.warning(
                "bleps_observer.feed_dark",
                communications_fault_pv=self._communications_fault_pv,
                detail="BLEPS observations suppressed until the comms flag reads clear",
            )
        elif not lost and self._reported_dark:
            self._reported_dark = False
            _log.info("bleps_observer.feed_restored")
        return lost

    def _verdict(
        self, channels: Sequence[BlepsChannel], latest: Mapping[str, bool | None]
    ) -> tuple[tuple[str, str], ...] | None:
        """Fold channels into culprits, or `None` when nothing can be said.

        Returns a tuple of `(label, trip_pv)` for every believable
        channel that is tripped. An EMPTY tuple means every channel is
        believable and clear. `None` means the verdict is inconclusive.

        The asymmetry is the safety property (see the module docstring):
        one believable trip is enough to call the Supply down, but a
        single unbelievable channel is enough to withhold "clear".
        """
        culprits: list[tuple[str, str]] = []
        blind = False
        for channel in channels:
            if channel.fault_pv and latest.get(channel.fault_pv) is not False:
                blind = True  # instrument faulted, or its fault flag unread
                continue
            trip = latest.get(channel.trip_pv)
            if trip is None:
                blind = True  # unread, or read but not believable
                continue
            if trip:
                culprits.append((channel.label, channel.trip_pv))
        if culprits:
            return tuple(culprits)
        return None if blind else ()

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
        aggregate unable to conclude anything.

        ANY failure voids the reading, not just a disconnect. The port has
        no single base error class, only a closed tuple private to the
        Conductor, and duplicating that tuple here is precisely the drift
        its own fitness test exists to catch. Nothing is lost by being
        broad: an unroutable address, a coercion failure and an adapter
        bug are all equally reasons to stop believing a channel, so the
        distinction would only change the log level. What matters is that
        the failure is recorded and the channel voided rather than
        escaping into `asyncio.gather(return_exceptions=True)`, where it
        would be discarded unseen and leave a stale reading standing.
        """
        try:
            async for reading in self._control_port.subscribe(pv):
                state = flag_state_from_reading(reading)
                if state is None and reading.quality == "Good":
                    # Good quality and still unreadable means the record
                    # is not shaped the way this adapter expects, most
                    # likely an enum label. Loud, because the alternative
                    # is a monitor that looks healthy and reports nothing.
                    _log.warning(
                        "bleps_observer.uninterpretable_flag",
                        pv=pv,
                        value=repr(reading.value),
                        kind=reading.kind,
                        detail="expected a numeric flag; this channel is excluded",
                    )
                queue.put_nowait((pv, state))
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("bleps_observer.channel_lost", pv=pv)
            queue.put_nowait((pv, None))
        finally:
            queue.put_nowait(_PUMP_DONE)


__all__ = ["BlepsChannel", "BlepsSupplyObserver", "flag_state_from_reading"]
