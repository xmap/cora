"""Per-call GPU-time attribution under concurrent serving.

The built serving path runs an open model on facility GPUs. In the
locked design in-house serving is metered-free by default (the debit,
when a facility toggles it on, stays token-priced), so this module is
VISIBILITY, not the debit: it reports how much GPU time each call
actually consumed, so a facility can watch shadow cost and capacity and
decide when in-house volume is worth revisiting. It never feeds the
budget gate.

The measurement problem it solves is real. Under continuous batching
many calls occupy one device at once, so attributing each call its full
wall-clock duration double-counts: four calls that share a GPU for one
second would report four GPU-seconds for one second of hardware.

This module attributes the shared time honestly. At every instant the
GPU-second is divided among the calls in flight, weighted; each call
accrues its share. The scheme is processor-sharing, the same fair
division long used for CPU-second accounting, and it carries one
exactness guarantee that makes the measurement trustworthy:

    For each device, the per-call shares sum to the device's busy
    wall-time (the measure of the union of the call intervals).

So the reported GPU-seconds never exceed what the hardware ran, and no
call's share exceeds its own duration. That per-call ceiling is a
property of the measure that keeps the shadow-cost figure honest (and
would license a solo GPU-hour pre-estimate only IF a facility ever chose
to debit GPU-hours, which the locked design defers).

## Equal versus weighted division

The default divides each shared instant equally. This is not only
convenient: during the decode phase of continuous-batched inference
every active sequence advances by about one token per forward step, so
the instantaneous work of the in-flight calls is roughly equal. A
facility that prefers a different work proxy (prompt length, to charge
the prefill-heavy call more) sets a per-call `weight`; the exactness
guarantee holds for any positive weights, because each shared instant
distributes its full length however it is split.

## Two forms

`attribute_occupancy_share` is a batch pure function over a whole set of
intervals: the reconciliation oracle, and the deterministic target the
property tests pin the online form against. `OccupancyShareMeter` is the
online accumulator the serving adapter drives: it finalizes a call's
share the instant the call ends, which is exact because every call that
overlapped it has by then started, and any still in flight covers the
whole elapsed window up to that instant.

Time is supplied by the caller (monotonic seconds from an injected
clock); this module never reads a clock itself, so both forms are pure
functions of their inputs and reproduce identically in a test, in
production, and in an after-the-fact reconciliation. Turning the
attributed GPU-seconds into an indicative shadow cost is a facility /
observability concern, not this module's, and the locked design adds no
GPU-hour branch to the cost path: here the unit is seconds throughout.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        msg = f"{name} must be finite, got {value}"
        raise ValueError(msg)


def _require_positive_finite_weight(value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        msg = f"weight must be positive and finite, got {value}"
        raise ValueError(msg)


@dataclass(frozen=True)
class ServedInterval:
    """One served call's occupancy of one device.

    `start_s` and `end_s` are monotonic seconds from the serving
    adapter's injected clock; `end_s >= start_s`. `weight` is the call's
    share of each instant it is in flight, relative to its concurrent
    peers (default equal, and positive finite); a call that never
    overlaps a peer is charged `end_s - start_s` whatever its weight.
    """

    call_id: str
    device_id: str
    start_s: float
    end_s: float
    weight: float = 1.0

    def __post_init__(self) -> None:
        _require_finite("start_s", self.start_s)
        _require_finite("end_s", self.end_s)
        _require_positive_finite_weight(self.weight)
        if self.end_s < self.start_s:
            msg = (
                f"served interval {self.call_id!r} ends before it starts: "
                f"{self.start_s} -> {self.end_s}"
            )
            raise ValueError(msg)


def attribute_occupancy_share(intervals: Iterable[ServedInterval]) -> dict[str, float]:
    """Attribute per-call GPU-seconds by weighted processor-sharing.

    Returns a mapping from `call_id` to the GPU-seconds it is charged,
    with every supplied `call_id` present (a zero-duration call maps to
    `0.0`). Calls on different devices never share, so the computation
    runs per device: for each device the timeline is cut at every start
    and end, and each resulting slice's length is divided among the
    calls live across the whole slice in proportion to their weights.

    Per device the returned charges sum to the union of the intervals
    (the device's busy wall-time), to within floating-point error. Two
    intervals that share a `call_id` (a retried call, say) accumulate
    into one total.
    """
    by_device: dict[str, list[ServedInterval]] = {}
    charges: dict[str, float] = {}
    for interval in intervals:
        by_device.setdefault(interval.device_id, []).append(interval)
        charges.setdefault(interval.call_id, 0.0)

    for device_intervals in by_device.values():
        _accrue_device(device_intervals, charges)
    return charges


def _accrue_device(intervals: list[ServedInterval], charges: dict[str, float]) -> None:
    """Sweep one device's timeline, crediting each slice to its live calls.

    Boundaries are every distinct start and end, so within a slice no
    call opens or closes: a call is live across the slice exactly when it
    starts at or before the slice's left edge and ends at or after its
    right edge.
    """
    boundaries = sorted({iv.start_s for iv in intervals} | {iv.end_s for iv in intervals})
    for left, right in itertools.pairwise(boundaries):
        span = right - left
        if span <= 0.0:
            continue
        live = [iv for iv in intervals if iv.start_s <= left and iv.end_s >= right]
        total_weight = math.fsum(iv.weight for iv in live)
        if total_weight <= 0.0:
            continue
        for iv in live:
            charges[iv.call_id] += span * iv.weight / total_weight


@dataclass
class _LiveCall:
    device_id: str
    weight: float
    accrued_s: float


class OccupancyShareMeter:
    """Online weighted processor-sharing accumulator for served calls.

    The serving adapter calls `open` when a request begins occupying a
    device and `close` when it releases it, passing monotonic seconds
    from its injected clock; `close` returns the call's final GPU-second
    charge. The results match `attribute_occupancy_share` over the same
    events exactly (a property test pins this).

    Concurrency is per device: `open` and `close` advance only the
    device the call is on, so calls on different devices never dilute
    each other. The meter holds only the currently-live calls, so its
    memory is bounded by peak concurrency, not by total calls served.
    """

    def __init__(self) -> None:
        self._live: dict[str, _LiveCall] = {}
        self._device_clock: dict[str, float] = {}
        self._device_weight: dict[str, float] = {}

    def open(self, call_id: str, *, device_id: str, at_s: float, weight: float = 1.0) -> None:
        """Record that `call_id` begins occupying `device_id` at `at_s`."""
        _require_finite("at_s", at_s)
        _require_positive_finite_weight(weight)
        if call_id in self._live:
            msg = f"call {call_id!r} is already open on this meter"
            raise ValueError(msg)
        self._advance(device_id, at_s)
        self._live[call_id] = _LiveCall(device_id=device_id, weight=weight, accrued_s=0.0)
        self._device_weight[device_id] = self._device_weight.get(device_id, 0.0) + weight

    def close(self, call_id: str, *, at_s: float) -> float:
        """Finalize `call_id` at `at_s` and return its GPU-second charge."""
        _require_finite("at_s", at_s)
        live = self._live.get(call_id)
        if live is None:
            msg = f"call {call_id!r} is not open on this meter"
            raise ValueError(msg)
        self._advance(live.device_id, at_s)
        del self._live[call_id]
        self._device_weight[live.device_id] -= live.weight
        return live.accrued_s

    def _advance(self, device_id: str, to_s: float) -> None:
        """Credit the elapsed slice since this device's last event to its live calls."""
        last = self._device_clock.get(device_id)
        if last is None:
            self._device_clock[device_id] = to_s
            return
        if to_s < last:
            msg = f"device {device_id!r} clock went backward: {last} -> {to_s}"
            raise ValueError(msg)
        self._device_clock[device_id] = to_s
        elapsed = to_s - last
        if elapsed == 0.0:
            return
        total_weight = self._device_weight.get(device_id, 0.0)
        if total_weight <= 0.0:
            return
        for live in self._live.values():
            if live.device_id == device_id:
                live.accrued_s += elapsed * live.weight / total_weight


__all__ = [
    "OccupancyShareMeter",
    "ServedInterval",
    "attribute_occupancy_share",
]
