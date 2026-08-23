"""SupplyObserver port: substrate-driven Supply-status observation stream.

`SupplyObserver` is the BC-local async Protocol the Supply BC's
monitor-trigger runtime uses to drain status observations from the
substrate (EPICS PV monitors, PVA subscriptions, Tango attribute
callbacks). Substrate details live behind concrete adapters; the
runtime never touches substrate-specific symbols.

Shaped after `cora.enclosure.ports.enclosure_observer`, which is the
in-codebase precedent for a monitor-trigger seam, and BC-local for the
same three reasons: the sole consumer is this BC's own runtime, the
seam is substrate-IO rather than cross-BC contract, and no other BC
reads observations off it.

## Only a status, never a severity

The observation carries a `SupplyStatus` string and nothing else about
how bad things are. Substrate severity vocabularies are flattened by
the adapter before crossing this seam: no `severity`, no `alarm_class`,
no `vendor_status_code`. Severity bookkeeping belongs to the substrate.

This matters more than it looks for the first real consumer. BLEPS
sorts its channels into warnings, trips and faults, but those are not
one scale (see [[project_bleps_ingest_design]]): warning and trip
answer "how bad is the measured value" while fault answers "is the
reading believable at all". Only the first question maps onto a
`SupplyStatus`. An adapter that decides a reading is not believable
must NOT emit an observation at all; there is no status value meaning
"I cannot tell", and inventing one would flatten a trust problem onto
the availability scale. Withholding is how this port says "unknown".

## What a monitor may and may not drive

The decider fences `Available`, `Unknown` and `Decommissioned` out of
the monitor path, so an adapter can only ever drive a Supply toward
`Degraded`, `Unavailable` or `Recovering`. Coming all the way back to
`Available` is an operator's word (`restore_supply`), on the latched-
alarm precedent in [[project_supply_design]]. An adapter that observes
a resource looking healthy again therefore emits `Recovering`, not
`Available`, and a person confirms.

## Stub roster

`AlwaysQuietSupplyObserver` ships inline at the bottom of this module:
the zero-substrate stub for tests, standing in for a beamline where
nothing is wrong. It yields NOTHING, and the name says so, following
`AlwaysQuietCautionLookup` rather than the `All<Predicate>Lookup`
family: those quantify over a set, this one describes a stream's
posture. An earlier name said `AllAvailable`, which was worse than
imprecise, because `Available` is the one status a monitor may never
drive, so the name promised the forbidden thing and then spent a
paragraph unsaying it.

## Subscribe shape

`observe` is a plain `def` returning `AsyncIterator[SupplyObservation]`
directly (no surrounding coroutine), matching the Enclosure port.
Connect setup may happen lazily on the first `__anext__`. Mid-stream
disconnect is the adapter's concern: production adapters re-raise so
the runtime can reconnect.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cora.shared.reach import ReachTier


@dataclass(frozen=True)
class SupplyObservation:
    """One status reading, or reach probe, drained from the substrate.

    `supply_code` is the BC-local Supply identity surface adapters
    know. The Supply address is a four-tuple
    (`facility_code`, `containing_asset_id`, `kind`, `name`), which is
    more than an adapter should have to assemble, so the runtime is
    handed a `{supply_code: supply_id}` map and adapters name the
    resource by its code alone. At 2-BM the codes are the Supply names
    (`2-BM cooling water`, `2-BM beamline vacuum`).

    `observed_status` is the raw status string the adapter produced
    after flattening whatever the substrate said. The runtime parses it
    against the `SupplyStatus` codomain and skips the observation if it
    does not match, so an adapter must not invent values. `None` means
    this observation is probe-only and makes no status claim at all:
    the aggregating verdict this tick was inconclusive (some channel
    behind this Supply could not be believed), which is a fact worth
    recording in the probe trail even though nothing can be said about
    the Supply's actual status. A `None` status never causes a Supply
    transition, by construction: there is nothing to parse.

    `reach_tier` is required, not optional, mirroring the Enclosure
    seam: it grades CORA's own reach to the substrate this tick,
    independent of what (if anything) was believed. `RELAYED` on every
    real verdict (tripped or clear -- a channel spoke and was believed);
    `UNREACHED` on the inconclusive case (a channel behind this Supply
    could not be believed, or the whole feed is dark).

    `observed_at` is the adapter's wall-clock at observation time,
    carried for diagnostics and for adapters that batch. The runtime
    does NOT use it as the event's `occurred_at`: a substrate-supplied
    timestamp could backdate an event past ones already appended, so
    ordering stays on the trusted clock. See the watch item in
    [[project_bleps_ingest_design]].

    `reason` is the adapter's human-readable account of what it saw
    ("Flow2 below set point"). It lands verbatim in the transition's
    reason when `observed_status` is set, which is where the per-channel
    detail lives: the status says a run cannot draw on the resource, the
    reason says which of the eight circuits said so. Unused (and may be
    empty) on a probe-only observation, since no transition reads it.

    `source_kind` and `source_id` ship as separate strings and are
    joined into the colon-delimited `monitor_ref` payload string by the
    runtime, matching the Enclosure seam.
    """

    supply_code: str
    observed_status: str | None
    reach_tier: ReachTier
    observed_at: datetime
    reason: str
    source_kind: str
    source_id: str


@dataclass(frozen=True)
class SupplyObserverScope:
    """Subscription scope: the set of supply codes to observe.

    Empty scope is valid and yields no observations (the adapter exits
    the iterator immediately). Adapters MUST NOT silently widen the
    subscription beyond the supplied scope.
    """

    supply_codes: frozenset[str]


class SupplyObserver(Protocol):
    """Async source of `SupplyObservation` values from the substrate.

    Not `@runtime_checkable`, unlike `EnclosureObserver`: nothing does
    an `isinstance` conformance check against this port, and the port
    fitness test requires the decorator and such a check to travel
    together so dead decorators do not accumulate. Add it if and when a
    runtime check appears.

    The substrate adapter owns the subscription lifecycle. The runtime
    iterates and records each observation as a Supply transition.

    Iteration semantics (identical to `EnclosureObserver`):

      - The iterator is open-ended for live substrates; callers either
        `async for` it for the runtime's lifetime or cancel the task to
        tear down the subscription.
      - One-shot observers (tests, stubs) MAY exhaust the iterator
        after a finite number of observations; the runtime treats
        `StopAsyncIteration` as a clean teardown.
      - Disconnect handling is the adapter's concern; production
        adapters re-raise substrate disconnect errors through the
        iterator so the runtime can reconnect.
    """

    def observe(self, scope: SupplyObserverScope) -> AsyncIterator[SupplyObservation]:
        """Open an observation stream over the supplied scope."""
        ...


class AlwaysQuietSupplyObserver:
    """Stub `SupplyObserver` that observes nothing.

    The zero-substrate observer for tests, standing in for a beamline
    where every resource is fine. A beamline with nothing wrong produces
    no readings, so silence is the faithful representation, and it is
    also the only safe one: `Available` is fenced out of the monitor path
    (only an operator restores a Supply), so a stub that yielded it would
    raise on every tick.
    """

    def observe(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        return self._drain(scope)

    async def _drain(self, scope: SupplyObserverScope) -> AsyncGenerator[SupplyObservation]:
        return
        yield  # pragma: no cover - unreachable, makes this an async generator


__all__ = [
    "AlwaysQuietSupplyObserver",
    "ReachTier",
    "SupplyObservation",
    "SupplyObserver",
    "SupplyObserverScope",
]
