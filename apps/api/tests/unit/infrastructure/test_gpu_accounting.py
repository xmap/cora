"""Unit and property tests for concurrent GPU-hour attribution."""

import math
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cora.infrastructure.observability.gpu_accounting import (
    OccupancyShareMeter,
    ServedInterval,
    attribute_occupancy_share,
)


def _iv(
    call_id: str,
    start_s: float,
    end_s: float,
    *,
    device_id: str = "gpu0",
    weight: float = 1.0,
) -> ServedInterval:
    return ServedInterval(
        call_id=call_id,
        device_id=device_id,
        start_s=start_s,
        end_s=end_s,
        weight=weight,
    )


def _union_measure(intervals: list[ServedInterval]) -> float:
    """Busy wall-time of one device: the measure of the union of its intervals."""
    segments = sorted((iv.start_s, iv.end_s) for iv in intervals if iv.end_s > iv.start_s)
    total = 0.0
    cur_start: float | None = None
    cur_end: float | None = None
    for start, end in segments:
        if cur_end is None:
            cur_start, cur_end = start, end
        elif start > cur_end:
            total += cur_end - (cur_start or 0.0)
            cur_start, cur_end = start, end
        else:
            cur_end = max(cur_end, end)
    if cur_end is not None:
        total += cur_end - (cur_start or 0.0)
    return total


# ---------------------------------------------------------------------------
# Batch attribution: hand-checked scenarios
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_single_call_charged_its_full_duration() -> None:
    charges = attribute_occupancy_share([_iv("a", 0.0, 10.0)])
    assert charges == {"a": pytest.approx(10.0)}


@pytest.mark.unit
def test_serial_calls_each_charged_full_duration() -> None:
    """Non-overlapping calls never share, so each keeps its whole duration."""
    charges = attribute_occupancy_share([_iv("a", 0.0, 10.0), _iv("b", 10.0, 25.0)])
    assert charges["a"] == pytest.approx(10.0)
    assert charges["b"] == pytest.approx(15.0)


@pytest.mark.unit
def test_two_full_overlap_split_evenly() -> None:
    """Two calls sharing a device for the same 10s bill 5s each, not 10s each."""
    charges = attribute_occupancy_share([_iv("a", 0.0, 10.0), _iv("b", 0.0, 10.0)])
    assert charges["a"] == pytest.approx(5.0)
    assert charges["b"] == pytest.approx(5.0)
    assert sum(charges.values()) == pytest.approx(10.0)


@pytest.mark.unit
def test_k_fold_full_overlap_split_evenly() -> None:
    """Four identical calls each pay a quarter; the sum is the one real GPU-second."""
    intervals = [_iv(f"c{i}", 0.0, 8.0) for i in range(4)]
    charges = attribute_occupancy_share(intervals)
    for i in range(4):
        assert charges[f"c{i}"] == pytest.approx(2.0)
    assert sum(charges.values()) == pytest.approx(8.0)


@pytest.mark.unit
def test_partial_overlap_matches_hand_computation() -> None:
    """a=[0,10], b=[5,15]: each is solo for 5s and shared for 5s -> 7.5s each."""
    charges = attribute_occupancy_share([_iv("a", 0.0, 10.0), _iv("b", 5.0, 15.0)])
    assert charges["a"] == pytest.approx(7.5)
    assert charges["b"] == pytest.approx(7.5)
    assert sum(charges.values()) == pytest.approx(15.0)


@pytest.mark.unit
def test_calls_on_distinct_devices_do_not_share() -> None:
    """Same wall-clock window but different GPUs: no dilution, each pays full."""
    charges = attribute_occupancy_share(
        [_iv("a", 0.0, 10.0, device_id="gpu0"), _iv("b", 0.0, 10.0, device_id="gpu1")]
    )
    assert charges["a"] == pytest.approx(10.0)
    assert charges["b"] == pytest.approx(10.0)


@pytest.mark.unit
def test_weighted_overlap_splits_in_proportion() -> None:
    """Weights 3 and 1 over the same 10s window bill 7.5s and 2.5s."""
    charges = attribute_occupancy_share(
        [_iv("heavy", 0.0, 10.0, weight=3.0), _iv("light", 0.0, 10.0, weight=1.0)]
    )
    assert charges["heavy"] == pytest.approx(7.5)
    assert charges["light"] == pytest.approx(2.5)
    assert sum(charges.values()) == pytest.approx(10.0)


@pytest.mark.unit
def test_zero_duration_call_is_present_and_charged_zero() -> None:
    charges = attribute_occupancy_share([_iv("a", 5.0, 5.0), _iv("b", 0.0, 10.0)])
    assert charges["a"] == pytest.approx(0.0)
    assert charges["b"] == pytest.approx(10.0)


@pytest.mark.unit
def test_interval_ending_before_it_starts_is_rejected() -> None:
    with pytest.raises(ValueError, match="ends before it starts"):
        _iv("a", 10.0, 5.0)


@pytest.mark.unit
def test_non_positive_weight_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive and finite"):
        _iv("a", 0.0, 10.0, weight=0.0)


# ---------------------------------------------------------------------------
# Online meter: hand-checked scenarios and misuse
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_meter_matches_batch_on_partial_overlap() -> None:
    """The online form reproduces the 7.5/7.5 partial-overlap split."""
    meter = OccupancyShareMeter()
    meter.open("a", device_id="gpu0", at_s=0.0)
    meter.open("b", device_id="gpu0", at_s=5.0)
    charge_a = meter.close("a", at_s=10.0)
    charge_b = meter.close("b", at_s=15.0)
    assert charge_a == pytest.approx(7.5)
    assert charge_b == pytest.approx(7.5)


@pytest.mark.unit
def test_meter_reopen_before_close_is_rejected() -> None:
    meter = OccupancyShareMeter()
    meter.open("a", device_id="gpu0", at_s=0.0)
    with pytest.raises(ValueError, match="already open"):
        meter.open("a", device_id="gpu0", at_s=1.0)


@pytest.mark.unit
def test_meter_close_of_unopened_call_is_rejected() -> None:
    meter = OccupancyShareMeter()
    with pytest.raises(ValueError, match="is not open"):
        meter.close("ghost", at_s=1.0)


@pytest.mark.unit
def test_meter_backward_clock_is_rejected() -> None:
    meter = OccupancyShareMeter()
    meter.open("a", device_id="gpu0", at_s=10.0)
    with pytest.raises(ValueError, match="clock went backward"):
        meter.close("a", at_s=5.0)


# ---------------------------------------------------------------------------
# Property tests: the guarantees the scheme rests on
# ---------------------------------------------------------------------------


@st.composite
def _single_device_intervals(
    draw: st.DrawFn, *, weighted: bool = False
) -> list[ServedInterval]:
    count = draw(st.integers(min_value=0, max_value=6))
    intervals: list[ServedInterval] = []
    for i in range(count):
        start = draw(st.integers(min_value=0, max_value=20))
        duration = draw(st.integers(min_value=0, max_value=20))
        weight = draw(st.integers(min_value=1, max_value=5)) if weighted else 1
        intervals.append(
            _iv(f"c{i}", float(start), float(start + duration), weight=float(weight))
        )
    return intervals


@st.composite
def _multi_device_intervals(
    draw: st.DrawFn, *, weighted: bool = False
) -> list[ServedInterval]:
    count = draw(st.integers(min_value=0, max_value=6))
    intervals: list[ServedInterval] = []
    for i in range(count):
        start = draw(st.integers(min_value=0, max_value=20))
        duration = draw(st.integers(min_value=0, max_value=20))
        device = draw(st.sampled_from(["gpu0", "gpu1", "gpu2"]))
        weight = draw(st.integers(min_value=1, max_value=5)) if weighted else 1
        intervals.append(
            _iv(
                f"c{i}",
                float(start),
                float(start + duration),
                device_id=device,
                weight=float(weight),
            )
        )
    return intervals


@pytest.mark.unit
@settings(max_examples=300, deadline=None)
@given(_single_device_intervals(weighted=True))
def test_charges_sum_to_device_busy_time(intervals: list[ServedInterval]) -> None:
    """The exactness guarantee: never bill more GPU-seconds than the GPU ran."""
    charges = attribute_occupancy_share(intervals)
    assert math.isclose(
        sum(charges.values()), _union_measure(intervals), rel_tol=1e-9, abs_tol=1e-9
    )


@pytest.mark.unit
@settings(max_examples=300, deadline=None)
@given(_multi_device_intervals(weighted=True))
def test_no_call_is_charged_more_than_its_own_duration(
    intervals: list[ServedInterval],
) -> None:
    """Sharing only lowers a charge, which is what makes the solo pre-estimate a ceiling."""
    charges = attribute_occupancy_share(intervals)
    for interval in intervals:
        duration = interval.end_s - interval.start_s
        assert charges[interval.call_id] <= duration + 1e-9


@pytest.mark.unit
@settings(max_examples=200, deadline=None)
@given(_multi_device_intervals(weighted=True), st.randoms(use_true_random=False))
def test_attribution_is_independent_of_input_order(
    intervals: list[ServedInterval], rng: random.Random
) -> None:
    shuffled = list(intervals)
    rng.shuffle(shuffled)
    assert attribute_occupancy_share(intervals) == attribute_occupancy_share(shuffled)


@pytest.mark.unit
@settings(max_examples=300, deadline=None)
@given(_multi_device_intervals(weighted=True))
def test_online_meter_reproduces_batch_attribution(
    intervals: list[ServedInterval],
) -> None:
    """The adapter-driven online meter equals the batch oracle event-for-event."""
    batch = attribute_occupancy_share(intervals)

    # Event-time order, opens before closes at a tie so a zero-duration
    # call opens before it closes and touching intervals never overlap
    # across a positive slice (the shared instant carries zero elapsed).
    events: list[tuple[float, int, ServedInterval]] = []
    for interval in intervals:
        events.append((interval.start_s, 0, interval))
        events.append((interval.end_s, 1, interval))
    events.sort(key=lambda event: (event[0], event[1]))

    meter = OccupancyShareMeter()
    online: dict[str, float] = {}
    for at_s, kind, interval in events:
        if kind == 0:
            meter.open(
                interval.call_id,
                device_id=interval.device_id,
                at_s=at_s,
                weight=interval.weight,
            )
        else:
            online[interval.call_id] = meter.close(interval.call_id, at_s=at_s)

    for call_id, batch_charge in batch.items():
        assert math.isclose(online[call_id], batch_charge, rel_tol=1e-9, abs_tol=1e-9)
