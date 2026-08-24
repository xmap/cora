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

Warnings are wired, gated off by default. See "Warnings, gated off by
default" below.

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

## Probe ticks: one poller per Supply, reading every channel

When `probe_tick_seconds` is configured, each Supply in scope also gets
a sibling polling task (`_poll`) alongside the per-PV push subscriptions
(`_pump`), both feeding the same queue. EPICS CA monitors are
change-only, so a beamline where nothing is happening produces no
readings at all after the initial connect, and the trail would then show
a gap that reads as a coverage outage when CORA was in fact still
watching. That is the exact ambiguity this seam exists to resolve.

The tick is scoped to a SUPPLY, not to a PV, because that is what a
probe row is keyed by and what a reader of the trail is asking about.
It reads every PV behind that Supply (each channel's fault, trip and
warning, plus the system-wide comms flag, which gates this Supply's
verdict as much as its own channels do) and writes ONE row: `RELAYED`
only if every one of them answered, `UNREACHED` naming the first that
did not. That all-or-nothing grading is the same asymmetry `_verdict`
already applies, for the same reason: losing sight of any one channel
costs the Supply its claim to being seen, because a trail that says
"watched" while a circuit is dark is worth less than no trail at all.
Per-PV rows were the alternative and would multiply two rows a tick into
thirty-two without answering a question the aggregate row leaves open.

The poller is a SIBLING of the pumps rather than nested inside one, for
the reason the enclosure precedent gives: a pump returns as soon as its
subscription ends, and `_drain` only re-subscribes once every pump has
returned, so a poller living inside a pump would die with it and could
never observe a recovery. As a sibling it keeps ticking through a dead
push path, and its probes are then the only remaining signal about which
specific PVs are unreachable.

A tick NEVER carries a status claim and never touches `latest`, so it
cannot move a Supply. That is a deliberate line rather than an omission.
It keeps exactly one path able to change a Supply's status, the push
path that carries the whole believability fold and all of its tests, and
it keeps `ReachTier`'s promise honest: a successful poll proves the
configured channels answered this tick, never that the verdict standing
in `latest` is current. Using poll reads to REFRESH `latest` would be a
different feature (repairing a silently dropped CA monitor update)
carrying its own unanswered question, what a failed read should do to a
value a subscription reported perfectly well a moment earlier, and
settling that by accident inside a coverage-trail change is how a
fail-open arrives unreviewed.

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
from cora.shared.quality import believable
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
    answer is load-bearing: a reading this function cannot believe or
    cannot interpret is not a LOW reading, and conflating the two would
    let a dead PV read as "no fault here".

    ## The quality floor is `Bad`, because on an interlock the alarm IS
    ## the signal

    This asks "can I believe this value", not "can I act on it", and for
    an equipment-protection interlock those come apart completely. A
    BLEPS record raises a MAJOR alarm PRECISELY WHEN ITS FLAG ASSERTS:
    that is what the alarm is for, to put the trip on an operator's
    screen. `EpicsCaControlPort` collapses MINOR and MAJOR to
    `Uncertain` (only INVALID is `Bad`, because only INVALID says the
    value itself is untrustworthy), so a `!= "Good"` floor here does not
    discard SOME readings, it discards EXACTLY THE ASSERTED ONES and
    keeps only the quiet ones. The observer could see a clear beamline
    and nothing else.

    Measured on arcturus 2026-08-23, 67 PVs, no exceptions, and stated
    PER ROLE because this one function reads three kinds of PV and they
    do not share a label pair:

      - process axis (`*_TRIP`, `*_WRN`, `NO_FAULT` / `TRIP`): every
        reading of `TRIP` carried `STATE MAJOR`; every `NO_FAULT`
        carried no alarm. All eight cooling-water circuits, three of
        seven vacuum sections, two ion pumps and six ion gauges were
        asserted, and a Good-only floor saw none of them.
      - trust axis (`*_OVER_RANGE`, `*_UNDER_RANGE`, `*_FAULTED`,
        `*_FAIL_TO_CLOSE`, `""` / `Present`): all sixteen read clear,
        all with no alarm.
      - system axis (`COMMUNICATIONS_FAULT`, same pair): clear, no
        alarm.

    The PSS agrees on the process axis: `S02BM-PSS:Sta[AB]:SecureM` and
    `SR-ACIS:2BM:FesPermitM` all sit at MAJOR while asserting. Nothing
    at 2-BM reported MINOR.

    What that sweep does NOT establish, and the difference matters for
    how far to trust the paragraph below: no trust-axis or system-axis
    flag was observed ASSERTED, because none were faulted that day. So
    "asserted implies MAJOR" is measured for the process axis and only
    inferred for the other two from the shared IOC template. The
    direction this function actually depends on is the other one, that
    a CLEAR reading carries no alarm, and that IS measured for all
    three.

    So the floor is `Bad`, matching `_enclosure_permit_observer`
    (loosened for this exact reason after 2-BM's SecureM read `Unknown`
    forever) and `_capture_baseline_reader` (which already records that
    "a MAJOR alarm is still a believable value"). Both of those wrote
    the principle down; this observer was written later and took the
    strict floor without asking which question it was answering.

    The loosening widens BOTH directions, and the second one deserves
    naming rather than burying. It can now call a Supply DOWN on an
    alarmed reading, which is the whole point. It can also now believe
    an alarmed CLEAR reading, which previously withheld the verdict, and
    that lands differently on each axis:

      - process axis: an alarmed clear trip flag counts toward "every
        channel clear", so a Supply can reach `Recovering` where it
        previously stayed silent.
      - trust axis: an alarmed clear `fault_pv` no longer blinds its
        channel, so that channel's trip reading is believed instead of
        being dropped from the fold (`_verdict`).
      - system axis: an alarmed clear comms flag no longer reads as a
        dark feed, so observations flow instead of being suppressed
        (`_communications_lost`).

    Each of those is a real widening, none is reachable on the measured
    2-BM data (every clear reading there carries no alarm, on all three
    axes), and all three are pinned by tests so a future facility where
    it IS reachable fails loudly rather than drifting. The counterweight
    is that the strict floor's conservatism was not free: it meant ANY
    standing alarm on a fault or comms record blinded the observer
    permanently, which is the same failure that made the process axis
    useless, just further upstream.

    CORA actuates nothing on any of these verdicts: it records what the
    interlock reported, and the interlock, not CORA, protects the
    equipment.

    ## Enum-valued records decode by index, not by label

    BLEPS flags are binary on the PLC side, but how they surface over
    Channel Access depends on the record type the IOC declares. A
    `longin` / `ai` arrives as a number. A `bi` / `mbbi` is `DBR_ENUM`,
    and `EpicsCaControlPort` resolves those to their FORMAT_CTRL label
    STRING while carrying the index it resolved from on
    `Measurement.ordinal`. `cora.shared.binary_signal.binary_code`
    reads the index first and treats its conventional label set
    (`ON` / `OFF`, `TRUE` / `FALSE`, `YES` / `NO`) as the fallback.

    BLEPS-4 IS ANSWERED, and reading by index is why this observer works
    at 2-BM at all. Measured on arcturus 2026-08-23 against the running
    `2bmBLEPS` IOC (`iocBoot/ioc2bmBLEPS/bleps.substitutions`, records
    built from `bleps_bi.db`): the trip and warning flags declare
    `ZNAM="NO_FAULT"` / `ONAM="TRIP"`, and the fault and comms flags
    declare `ZNAM=""` (the EMPTY STRING) / `ONAM="Present"`. Neither
    pair is in any conventional set, and `caget` returns those literal
    words, so a label-only reader resolves EVERY BLEPS channel to
    `None`: the comms flag included, which would then read as a dark
    feed and suppress the whole observer. The indices behind those
    labels are a plain 0 / 1, the same as any other facility's.

    So the labels are not decoded here and no BLEPS vocabulary is
    hardcoded anywhere in CORA. That is deliberate beyond this one IOC:
    `ZNAM` / `ONAM` are free text, nothing constrains them, and a
    facility is free to edit them for a nicer operator screen. The index
    is the half that does not move.
    """
    if not believable(reading.quality):
        return None
    code = binary_code(reading.value, ordinal=reading.ordinal)
    return None if code is None else code != 0


class _PumpDone:
    """Per-PV sentinel pushed onto the merge queue when a pump exits."""

    __slots__ = ()


_PUMP_DONE = _PumpDone()

# What travels the merge queue: a pump's per-PV believability reading, a
# poller's ready-made probe observation, or a pump's completion sentinel.
_QueueItem = tuple[str, bool | None] | SupplyObservation | _PumpDone


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
        probe_tick_seconds: float | None = None,
    ) -> None:
        self._control_port = control_port
        self._channels = tuple(channels)
        self._communications_fault_pv = communications_fault_pv
        self._clock = clock
        self._probe_tick_seconds = probe_tick_seconds
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
        all_supply_codes = frozenset(c.supply_code for c in channels)
        pv_supply_codes = self._pv_supply_codes(channels)
        # Latest believed value per PV. Absent means never read; None
        # means read but not believable. Both are "unknown", and neither
        # is "low". This is a read cache, not a verdict: it is rebuilt
        # from scratch on every re-subscribe and nothing is inferred from
        # its absence.
        latest: dict[str, bool | None] = {}

        queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        pump_tasks = [
            asyncio.create_task(self._pump(pv, queue), name=f"bleps-pump:{pv}") for pv in pvs
        ]
        poll_tasks = self._poll_tasks(channels, queue)
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
                if isinstance(item, SupplyObservation):
                    # A poll tick, already shaped. It bypasses `latest`
                    # and `_observations` entirely: a probe is a reach
                    # fact, not a reading, and folding one in would let a
                    # timer move a Supply.
                    yield item
                    continue
                pv, value = item
                latest[pv] = value
                # A reading affects only the Supply(s) its own channel
                # feeds, EXCEPT the comms flag, which is a fact about the
                # whole feed and so affects every configured Supply.
                # Scoping this way is what keeps the probe trail honest:
                # without it, any one Supply's chatty PV would refresh
                # every OTHER Supply's `entries_supply_probes` row too,
                # making a genuinely silent Supply look continuously
                # watched for as long as its siblings kept talking.
                affected = (
                    all_supply_codes
                    if pv == self._communications_fault_pv
                    else pv_supply_codes.get(pv, frozenset())
                )
                for observation in self._observations(
                    channels, latest, affected_supply_codes=affected
                ):
                    yield observation
            # Every pump has finished, but a still-running poller can have
            # enqueued a probe in the same instant the final `_PumpDone`
            # was read (`put_nowait` needs no await, so it is not ordered
            # against the `remaining` check above). Drain exactly what is
            # ALREADY queued, synchronously, into a list before yielding
            # any of it: yielding suspends this generator and hands
            # control back to a poller, which could otherwise keep
            # `qsize()` perpetually non-zero and stop `_drain` from ever
            # returning to let the runtime re-subscribe.
            #
            # Only probes can be left over, never readings: `remaining`
            # reaches zero only once every pump's `_PumpDone` has been
            # READ, and each pump queues its readings ahead of its own
            # sentinel, so FIFO order has already delivered them.
            leftover = [queue.get_nowait() for _ in range(queue.qsize())]
            for item in leftover:
                if isinstance(item, SupplyObservation):
                    yield item
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _subscribed_pvs(self, channels: Iterable[BlepsChannel]) -> list[str]:
        """Every PV behind `channels`: trust before process, system before channel.

        The comms flag comes first, then each channel's instrumentation
        fault ahead of its trip and warning. Order does not change any
        verdict now that "clear" requires every channel, but it still
        decides how quickly the first real verdict can form.

        Also the poller's read set, called there with one Supply's
        channels rather than all of them. The comms flag belongs in
        both: a Supply whose feed is dark cannot be assessed, so a tick
        that could not read it has not reached that Supply either.
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

    def _pv_supply_codes(self, channels: Iterable[BlepsChannel]) -> dict[str, frozenset[str]]:
        """Map each channel-owned PV to the Supply code(s) it feeds.

        Excludes the comms flag deliberately: that PV's effect is
        system-wide and `_drain` handles it as its own case, not via
        this per-channel map.
        """
        by_pv: dict[str, set[str]] = {}
        for channel in channels:
            for pv in (channel.fault_pv, channel.trip_pv, channel.warning_pv):
                if pv:
                    by_pv.setdefault(pv, set()).add(channel.supply_code)
        return {pv: frozenset(codes) for pv, codes in by_pv.items()}

    def _observations(
        self,
        channels: Sequence[BlepsChannel],
        latest: Mapping[str, bool | None],
        *,
        affected_supply_codes: frozenset[str],
    ) -> list[SupplyObservation]:
        """Recompute and report the affected Supplies' verdict, or their reach probe.

        Stateless, and scoped to `affected_supply_codes` (the Supply or
        Supplies the triggering reading's own channel feeds, or every
        configured Supply when the reading was the comms flag): a
        Supply not in scope gets no entry from this call at all, so an
        unrelated Supply's chatty channel can never refresh this one's
        `entries_supply_probes` row.

        Every affected Supply gets exactly one entry: a real verdict
        (`reach_tier=RELAYED`) when one can be concluded, or a probe-only
        entry (`observed_status=None`, `reach_tier=UNREACHED`) when it
        cannot. Silently emitting nothing for the inconclusive case, as
        an earlier version did, is exactly the coverage gap the probe
        trail exists to close: a Supply CORA cannot currently assess
        must not look identical, from the trail's perspective, to one
        nobody configured a channel for.
        """
        by_supply: dict[str, list[BlepsChannel]] = {}
        for channel in channels:
            if channel.supply_code in affected_supply_codes:
                by_supply.setdefault(channel.supply_code, []).append(channel)
        if self._communications_lost(latest):
            return [
                self._probe_only(
                    supply_code,
                    pv=supply_channels[0].trip_pv,
                    reach_tier=ReachTier.UNREACHED,
                )
                for supply_code, supply_channels in sorted(by_supply.items())
            ]
        observations: list[SupplyObservation] = []
        for supply_code, supply_channels in sorted(by_supply.items()):
            verdict = self._verdict(supply_channels, latest)
            if verdict is None:
                observations.append(
                    self._probe_only(
                        supply_code,
                        pv=supply_channels[0].trip_pv,
                        reach_tier=ReachTier.UNREACHED,
                    )
                )
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

    def _probe_only(self, supply_code: str, *, pv: str, reach_tier: ReachTier) -> SupplyObservation:
        """A reach fact with no status claim.

        Two callers, two different facts, one tier vocabulary.
        `_observations` builds these when a verdict is inconclusive and
        always grades them `UNREACHED`; `_poll` builds them on a timer
        and grades the tick itself. `ReachTier` measures reach, not its
        cause, so the two meanings share `UNREACHED` legitimately: the
        enclosure precedent overloads it the same way, for a failed poll
        and for a disconnect.

        `reason` is empty because nothing reads it: the runtime returns
        before building a transition command when `observed_status` is
        `None`. `pv` names the channel this probe row is attributed to;
        callers pass the Supply's first trip PV, mirroring how a real
        `Unavailable`/`Recovering` verdict already attributes to one
        representative channel rather than the whole set. `_poll`
        departs from that on failure alone, naming the PV that actually
        went unread, because an `UNREACHED` row is only actionable if it
        says which channel to go and look at.
        """
        return SupplyObservation(
            supply_code=supply_code,
            observed_status=None,
            reach_tier=reach_tier,
            observed_at=self._clock.now(),
            reason="",
            source_kind=_SOURCE_KIND,
            source_id=pv,
        )

    def _poll_tasks(
        self, channels: Sequence[BlepsChannel], queue: asyncio.Queue[_QueueItem]
    ) -> list[asyncio.Task[None]]:
        """One poller per in-scope Supply, or none when ticks are disabled.

        Grouping by Supply rather than by PV is what makes the tick's
        output one row per Supply per tick; see the module docstring.
        """
        if self._probe_tick_seconds is None:
            return []
        by_supply: dict[str, list[BlepsChannel]] = {}
        for channel in channels:
            by_supply.setdefault(channel.supply_code, []).append(channel)
        return [
            asyncio.create_task(
                self._poll(supply_code, supply_channels, queue),
                name=f"bleps-poll:{supply_code}",
            )
            for supply_code, supply_channels in sorted(by_supply.items())
        ]

    async def _poll(
        self,
        supply_code: str,
        channels: Sequence[BlepsChannel],
        queue: asyncio.Queue[_QueueItem],
    ) -> None:
        """Re-affirm reach to one Supply's whole channel set every tick.

        Never pushes `_PumpDone`: this task is a sibling of the pumps,
        not a stage in any pump's lifecycle, and runs until `_drain`'s
        `finally` cancels it on teardown. It ticks unconditionally,
        regardless of how much push traffic the channels are producing,
        which is simpler than gating on quiescence and avoids the "a
        chatty Supply is never polled" surprise that gating would carry.

        Reads are concurrent so the tick costs one round trip rather
        than thirty-two, and `return_exceptions=True` makes every
        per-PV failure a datum instead of an escape: a probe recording
        that CORA could not see a channel is the entire point, so there
        is nothing here to raise about. Hence no `except` clause, unlike
        `_pump`. Teardown still works: a cancellation aimed at THIS task
        propagates out of `gather` rather than being collected. A
        cancellation raised inside one read is collected like any other
        failure, which is the right reading of it, that channel went
        unread this tick.

        One row per tick, `RELAYED` only if every PV answered. A partial
        read is graded `UNREACHED` and attributed to the first PV that
        failed: reporting reach because some channels answered would put
        exactly the false coverage claim in the trail that the trail
        exists to rule out.
        """
        assert self._probe_tick_seconds is not None
        pvs = self._subscribed_pvs(channels)
        representative_pv = channels[0].trip_pv
        while True:
            await asyncio.sleep(self._probe_tick_seconds)
            results = await asyncio.gather(
                *(self._control_port.read(pv) for pv in pvs), return_exceptions=True
            )
            unread = [
                pv
                for pv, result in zip(pvs, results, strict=True)
                if isinstance(result, BaseException)
            ]
            if unread:
                _log.warning(
                    "bleps_observer.probe_unreached",
                    supply_code=supply_code,
                    unread_pvs=unread,
                    read_count=len(pvs),
                    detail="probe tick could not read every channel behind this supply",
                )
            queue.put_nowait(
                self._probe_only(
                    supply_code,
                    pv=unread[0] if unread else representative_pv,
                    reach_tier=ReachTier.UNREACHED if unread else ReachTier.RELAYED,
                )
            )

    async def _pump(self, pv: str, queue: asyncio.Queue[_QueueItem]) -> None:
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
                if state is None and believable(reading.quality):
                    # Tracks `flag_state_from_reading`'s floor rather than
                    # naming "Good" independently: an alarmed reading is
                    # believable here, so an alarmed one CORA still cannot
                    # resolve is exactly as loud a problem as a quiet one.
                    # Testing "Good" would have gone quiet for every
                    # asserted BLEPS flag, which is the population most
                    # worth hearing about.
                    #
                    # A believable reading CORA still cannot resolve. Two
                    # shapes reach here, and the ordinal tells them apart:
                    # with no ordinal the reading carried only a label
                    # outside the conventional set, which now means a
                    # genuine string record rather than the enum case
                    # BLEPS-4 covered; WITH an ordinal it is out of the
                    # two-state range, which says this channel is pointed
                    # at a record that is not a flag at all (an `mbbi`
                    # mid-vocabulary), a configuration error rather than a
                    # vocabulary one. Both are logged loudly because the
                    # alternative is a monitor that looks healthy and
                    # reports nothing.
                    _log.warning(
                        "bleps_observer.uninterpretable_flag",
                        pv=pv,
                        value=repr(reading.value),
                        kind=reading.kind,
                        ordinal=reading.ordinal,
                        detail=(
                            "not resolvable to a two-state flag: out-of-range ordinal, "
                            "or no ordinal and an unconventional label; excluded"
                        ),
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
