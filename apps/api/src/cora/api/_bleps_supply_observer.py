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

## Probes: an inconclusive verdict is a reach fact, not silence

The withhold case (a believable trip cannot be distinguished from an
unbelievable one, or the whole comms feed is dark) used to emit nothing
at all for the affected Supply. That is exactly the ambiguity the
probe trail exists to resolve: a Supply CORA cannot currently assess
must not look, from the trail's perspective, identical to one nobody
is watching. `_observations` now reports every configured Supply on
every call, either a real verdict (`reach_tier=RELAYED`) or a
probe-only entry (`observed_status=None`, `reach_tier=UNREACHED`).
`cora.supply._monitor` writes the probe row unconditionally and returns
before attempting a transition when `observed_status` is `None`, so a
withheld verdict never becomes a false Supply status.

## Warnings, gated off by default

The 30 warning channels map to `Degraded`, one severity rung below a
trip, following the same one-is-enough-to-degrade / all-must-clear
asymmetry `_verdict` already applies to trips. This was blocked at
first: `Degraded -> Available` was a one-way door in the shipped Supply
FSM (`restore_supply` accepted only `Recovering`), so a latched warning
nobody reset would have parked a resource in a state an operator could
not leave without first declaring it Unavailable. That gap closed when
`restore_supply` widened to accept `{Recovering, Degraded}`.

What is still open is not semantic but empirical: nobody has measured
how often BLEPS warnings actually latch at 2-BM. A channel that warns
routinely would still park its Supply in `Degraded` semi-permanently,
which fails the run-start supply gate (`Degraded` does not satisfy it).
Rather than block on staff answering that, warnings ship OFF by
default, gated by `Settings.bleps_supply_warnings_enabled`: this
adapter is unconditionally warning-AWARE (`BlepsChannel.warning_pv`,
`_verdict`'s second return element), but the composition root only
populates `warning_pv` when the flag is on. A deployment can flip it
and observe the real base rate directly instead of guessing at it.

A monitor can drive `Degraded` only from `{Unknown, Available,
Recovering}` (the decider's `_DEGRADABLE_SOURCES`), so a warning
observed while a Supply sits `Unavailable` from an earlier trip cannot
degrade it further; `cora.supply._monitor` skips that case before
attempting the command, mirroring its existing `Recovering`-vs-
`Unavailable` skip.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger
from cora.shared.binary_signal import binary_code
from cora.supply.ports.supply_observer import (
    ReachTier,
    SupplyObservation,
    SupplyObserverScope,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence

    from cora.infrastructure.ports import Clock
    from cora.operation.ports.control_port import ControlPort, Measurement

_SOURCE_KIND = "EpicsPv"
_UNAVAILABLE = "Unavailable"
_DEGRADED = "Degraded"
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
    channel's `trip_pv` AND `warning_pv` cannot be believed and the
    channel drops out of the verdict entirely. Valves and vacuum
    sections have no separate instrumentation fault, so this is `None`
    for them.

    `warning_pv` is the optional, less-severe process-axis PV on the
    same physical quantity as `trip_pv` (`Flow2.Under_Range_Warning`).
    Non-zero means the value has crossed the warning threshold but not
    yet the trip threshold. `None` when this channel's warning is not
    wired -- the default, gated by `Settings.bleps_supply_warnings_enabled`
    at the composition root (main.py never populates this field unless
    that flag is on), not by anything in this class.
    """

    supply_code: str
    label: str
    trip_pv: str
    fault_pv: str | None = None
    warning_pv: str | None = None


def flag_state_from_reading(reading: Measurement) -> bool | None:
    """Is this BLEPS flag high? `None` when the reading cannot be believed.

    Named `<value>_from_reading` rather than `is_*` because the third
    answer is load-bearing: a non-Good quality reading, or a value this
    function cannot interpret, is not a LOW reading, and conflating the
    two would let a dead PV read as "no fault here".

    ## Enum-valued records decode through the shared convention

    BLEPS flags are binary on the PLC side, but how they surface over
    Channel Access depends on the record type the IOC declares. A
    `longin` / `ai` arrives as a number. A `bi` / `mbbi` is `DBR_ENUM`,
    and `EpicsCaControlPort` resolves those to their FORMAT_CTRL label
    STRING, falling back to the stringified index when the label cache
    is cold. `cora.shared.binary_signal.binary_code` handles both
    shapes, matching the conventional EPICS binary labels (`ON` / `OFF`,
    `TRUE` / `FALSE`, `YES` / `NO`) the same way the enclosure permit,
    beam-availability and capture observers already do for their own
    `bi` records.

    It does NOT guess beyond that convention: a label outside it (a
    facility-chosen pair such as `"TRIP"` / `"OK"`, hypothesized but not
    confirmed here) still returns `None` rather than being mapped,
    because that would be inventing a fact about an IOC nobody here has
    read. The caller logs an unrecognized-but-Good reading loudly, and
    which label vocabulary the deployed BLEPS IOC actually uses is
    BLEPS-4, still open for staff to confirm.
    """
    if reading.quality != "Good":
        return None
    code = binary_code(reading.value)
    return None if code is None else code != 0


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
        fault ahead of its trip and warning. Order does not change any
        verdict now that "clear" requires every channel, but it still
        decides how quickly the first real verdict can form.
        """
        pvs: list[str] = []
        if self._communications_fault_pv:
            pvs.append(self._communications_fault_pv)
        for channel in channels:
            if channel.fault_pv:
                pvs.append(channel.fault_pv)
            pvs.append(channel.trip_pv)
            if channel.warning_pv:
                pvs.append(channel.warning_pv)
        # Dedupe, preserving that order.
        return list(dict.fromkeys(pvs))

    def _observations(
        self, channels: Sequence[BlepsChannel], latest: Mapping[str, bool | None]
    ) -> list[SupplyObservation]:
        """Recompute and report every Supply's verdict, or its reach probe. Stateless.

        Every configured Supply gets exactly one entry per call: a real
        verdict (`reach_tier=RELAYED`) when one can be concluded, or a
        probe-only entry (`observed_status=None`, `reach_tier=UNREACHED`)
        when it cannot. Silently emitting nothing for the inconclusive
        case, as an earlier version did, is exactly the coverage gap the
        probe trail exists to close: a Supply CORA cannot currently
        assess must not look identical, from the trail's perspective, to
        one nobody configured a channel for.
        """
        by_supply: dict[str, list[BlepsChannel]] = {}
        for channel in channels:
            by_supply.setdefault(channel.supply_code, []).append(channel)
        if self._communications_lost(latest):
            return [
                self._probe_only(supply_code, pv=supply_channels[0].trip_pv)
                for supply_code, supply_channels in sorted(by_supply.items())
            ]
        observations: list[SupplyObservation] = []
        for supply_code, supply_channels in sorted(by_supply.items()):
            verdict = self._verdict(supply_channels, latest)
            if verdict is None:
                observations.append(self._probe_only(supply_code, pv=supply_channels[0].trip_pv))
                continue
            trip_culprits, warning_culprits = verdict
            if trip_culprits:
                observations.append(
                    self._observation(
                        supply_code,
                        _UNAVAILABLE,
                        reason=f"BLEPS trip: {', '.join(label for label, _ in trip_culprits)}",
                        pv=trip_culprits[0][1],
                    )
                )
            elif warning_culprits:
                observations.append(
                    self._observation(
                        supply_code,
                        _DEGRADED,
                        reason=(
                            f"BLEPS warning: {', '.join(label for label, _ in warning_culprits)}"
                        ),
                        pv=warning_culprits[0][1],
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
    ) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]] | None:
        """Fold channels into `(trip_culprits, warning_culprits)`, or `None` when blind.

        Each element is a tuple of `(label, pv)` for every believable
        channel asserting that level. Both empty means every channel is
        believable and clear. `None` means the verdict is inconclusive.

        Trip dominates unconditionally: a believable trip anywhere is
        reported regardless of a sibling channel's blindness or warning
        state, exactly the pre-warning asymmetry (one believable trip is
        enough to call the Supply down; a single unbelievable channel is
        enough to withhold "clear"). Warning extends the SAME asymmetry
        one rung down: absent any trip, one believable warning anywhere
        is enough to call the Supply Degraded, and "clear" (both empty)
        still requires every channel's trip AND configured warning
        reading to be believable. A tripped channel's own warning
        reading is skipped: the same physical quantity cannot be both,
        and the trip already dominates.
        """
        trip_culprits: list[tuple[str, str]] = []
        warning_culprits: list[tuple[str, str]] = []
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
                trip_culprits.append((channel.label, channel.trip_pv))
                continue
            if channel.warning_pv is None:
                continue
            warning = latest.get(channel.warning_pv)
            if warning is None:
                blind = True  # unread, or read but not believable
                continue
            if warning:
                warning_culprits.append((channel.label, channel.warning_pv))
        if trip_culprits:
            return tuple(trip_culprits), ()
        if blind:
            return None
        return (), tuple(warning_culprits)

    def _observation(
        self, supply_code: str, status: str, *, reason: str, pv: str
    ) -> SupplyObservation:
        return SupplyObservation(
            supply_code=supply_code,
            observed_status=status,
            reach_tier=ReachTier.RELAYED,
            observed_at=self._clock.now(),
            reason=reason,
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _probe_only(self, supply_code: str, *, pv: str) -> SupplyObservation:
        """A reach fact with no status claim: the verdict was inconclusive.

        `reason` is empty because nothing reads it: the runtime returns
        before building a transition command when `observed_status` is
        `None`. `pv` names the channel this probe row is attributed to;
        callers pass the supply's first trip PV, mirroring how a real
        `Unavailable`/`Recovering` verdict already attributes to one
        representative channel rather than the whole set.
        """
        return SupplyObservation(
            supply_code=supply_code,
            observed_status=None,
            reach_tier=ReachTier.UNREACHED,
            observed_at=self._clock.now(),
            reason="",
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
                    # Good quality and still unreadable means the label
                    # is outside the conventional EPICS binary set
                    # `binary_code` matches (ON/OFF, TRUE/FALSE, YES/NO,
                    # 0/1) -- most likely BLEPS-4's open question, a
                    # facility-chosen label pair. Loud, because the
                    # alternative is a monitor that looks healthy and
                    # reports nothing.
                    _log.warning(
                        "bleps_observer.uninterpretable_flag",
                        pv=pv,
                        value=repr(reading.value),
                        kind=reading.kind,
                        detail="not a numeric flag or a conventional EPICS binary label; excluded",
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
