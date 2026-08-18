"""Enforcement-ladder characterization: measured overspend of the shipped gate.

Drives the real `find_allocation_breach` (the instrument-envelope arm of the
enforcement seam, `cora.agent._budget_gate`) over deterministic cost traces
and reports the overspend each tier admits. It is the committed, reproducible
source of the enforcement-ladder overspend figures; run

    python -m tests.unit.agent.test_enforcement_ladder_characterization

from `apps/api` to re-emit the JSON, or `pytest` this module to lock the figures
as a regression.

The environment is in-memory and deterministic: an accumulating ledger
(a `FakeSpendLookup` reconstructed with the running total per query) behind an
Active envelope (`FakeAllocationLookup`), event-time gating with no wall clock.
Two caller tiers are exercised, each serialized and raced:

  - coarse post-hoc (`pending_usd = 0`, the gate's `spent >= ceiling` arm),
  - per-call pre-estimate (`pending_usd` the call's estimate, the gate's
    `spent + pending > ceiling` arm).

The raced arrangement models two callers that both read the ledger before either
posts, the concurrency the shipped in-flight counter measures. Its headline is
that a perfect ceiling estimate bounds a SERIALIZED caller to zero overspend but
leaves a RACED pair over by one full call: the per-call pre-estimate bound is the
estimate's error PLUS one call per extra concurrent caller, not the error alone.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cora.agent._budget_gate import find_allocation_breach
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from tests.unit.agent._helpers import FakeAllocationLookup, FakeSpendLookup

if TYPE_CHECKING:
    from collections.abc import Callable

_NOW = datetime(2026, 7, 11, 15, 30, tzinfo=UTC)
_ACTIVATED_AT = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

CAP_USD = 100.0
SMALL_CALL_USD = 0.7
LARGE_CALL_USD = 20.0


# Estimate policies: pending_usd as a function of the call's true cost.
def _post_hoc(_cost: float) -> float:
    return 0.0


def _ceiling(cost: float) -> float:
    return cost


def _under_0_6x(cost: float) -> float:
    return 0.6 * cost


def _high_1_25x(cost: float) -> float:
    return 1.25 * cost


def _envelope(ceiling_usd: float = CAP_USD) -> AllocationLookupResult:
    return AllocationLookupResult(
        allocation_id=uuid4(),
        ceiling_usd=ceiling_usd,
        activated_at=_ACTIVATED_AT,
        campaign_id=None,
    )


async def _permitted(ledger: float, pending: float, ceiling: float) -> bool:
    """Ask the real gate whether a call projecting `pending` is admitted."""
    breach = await find_allocation_breach(
        allocation_lookup=FakeAllocationLookup(active=_envelope(ceiling)),
        spend_lookup=FakeSpendLookup(total_usd_spent=ledger),
        as_of=_NOW,
        pending_usd=pending,
    )
    return breach is None


def _summary(
    *,
    permitted: int,
    offered: int,
    final: float,
    ceiling: float,
    max_call: float,
    max_underestimate: float,
    report_estimate_error: bool,
) -> dict[str, float | int]:
    out: dict[str, float | int] = {
        "permitted_calls": permitted,
        "offered_calls": offered,
        "final_spent_usd": round(final, 4),
        "overspend_usd": round(max(0.0, final - ceiling), 4),
        "unused_headroom_usd": round(max(0.0, ceiling - final), 4),
        "max_call_usd": round(max_call, 4),
    }
    if report_estimate_error:
        out["max_estimate_error_usd"] = round(max_underestimate, 4)
    return out


async def _serial(
    calls: list[float],
    *,
    estimate: Callable[[float], float],
    ceiling: float = CAP_USD,
    initial: float = 0.0,
    report_estimate_error: bool = False,
) -> dict[str, float | int]:
    """Drive `calls` one at a time; each reads the ledger the prior one left."""
    ledger = initial
    permitted = 0
    max_call = 0.0
    max_underestimate = 0.0
    for cost in calls:
        pending = estimate(cost)
        if await _permitted(ledger, pending, ceiling):
            ledger += cost
            permitted += 1
            max_call = max(max_call, cost)
            max_underestimate = max(max_underestimate, max(0.0, cost - pending))
    return _summary(
        permitted=permitted,
        offered=len(calls),
        final=ledger,
        ceiling=ceiling,
        max_call=max_call,
        max_underestimate=max_underestimate,
        report_estimate_error=report_estimate_error,
    )


async def _raced(
    racers: list[float],
    *,
    estimate: Callable[[float], float],
    initial: float,
    ceiling: float = CAP_USD,
    report_estimate_error: bool = False,
) -> dict[str, float | int]:
    """Every racer reads the same `initial` ledger before any of them posts."""
    ledger = initial
    permitted = 0
    max_call = 0.0
    max_underestimate = 0.0
    for cost in racers:
        pending = estimate(cost)
        if await _permitted(initial, pending, ceiling):  # stale read: all see `initial`
            ledger += cost
            permitted += 1
            max_call = max(max_call, cost)
            max_underestimate = max(max_underestimate, max(0.0, cost - pending))
    return _summary(
        permitted=permitted,
        offered=len(racers),
        final=ledger,
        ceiling=ceiling,
        max_call=max_call,
        max_underestimate=max_underestimate,
        report_estimate_error=report_estimate_error,
    )


async def build_enforcement_ladder() -> dict[str, Any]:
    """Assemble the full ladder from live gate runs. The JSON source of truth."""
    uniform = [SMALL_CALL_USD] * 200
    large_tail = [SMALL_CALL_USD] * 142 + [LARGE_CALL_USD] * 6
    two_large = [LARGE_CALL_USD, LARGE_CALL_USD]
    return {
        "environment": (
            "in-memory: real find_allocation_breach over an accumulating ledger "
            "(FakeSpendLookup) behind an Active FakeAllocationLookup; deterministic, "
            "event-time gating (no wall clock)"
        ),
        "source": "apps/api/tests/unit/agent/test_enforcement_ladder_characterization.py",
        "cap_usd": CAP_USD,
        "small_call_usd": SMALL_CALL_USD,
        "large_call_usd": LARGE_CALL_USD,
        "tiers": {
            "coarse_post_hoc": {
                "bound": "one in-flight call per caller",
                "uniform": await _serial(uniform, estimate=_post_hoc),
                "large_tail": await _serial(large_tail, estimate=_post_hoc),
            },
            "per_call_pre_estimate": {
                "bound": "underestimate error; zero under a serialized ceiling estimate",
                "ceiling_large_tail": await _serial(
                    large_tail, estimate=_ceiling, report_estimate_error=True
                ),
                "underestimate_0_6x_uniform": await _serial(
                    uniform, estimate=_under_0_6x, report_estimate_error=True
                ),
                "high_biased_1_25x_uniform": await _serial(
                    uniform, estimate=_high_1_25x, report_estimate_error=True
                ),
            },
            "instrument_envelope_post_hoc": {
                "bound": "one in-flight call per CALLER, not per envelope",
                "serialized_two_callers": await _serial(
                    two_large, estimate=_post_hoc, initial=99.4
                ),
                "raced_two_callers": await _raced(two_large, estimate=_post_hoc, initial=99.4),
            },
            "instrument_envelope_pre_estimate": {
                "bound": "the estimate's error PLUS one call per extra concurrent caller",
                "serialized_two_callers": await _serial(
                    two_large, estimate=_ceiling, initial=80.0, report_estimate_error=True
                ),
                "raced_two_callers": await _raced(
                    two_large, estimate=_ceiling, initial=80.0, report_estimate_error=True
                ),
            },
        },
    }


# ---------- Regression locks on the headline figures ----------


@pytest.mark.unit
async def test_coarse_post_hoc_leaks_at_most_one_in_flight_call() -> None:
    tiers = (await build_enforcement_ladder())["tiers"]["coarse_post_hoc"]
    assert tiers["uniform"]["overspend_usd"] == pytest.approx(0.1, abs=1e-6)
    assert tiers["large_tail"]["overspend_usd"] == pytest.approx(19.4, abs=1e-6)


@pytest.mark.unit
async def test_pre_estimate_serialized_bound_is_the_underestimate_error() -> None:
    tiers = (await build_enforcement_ladder())["tiers"]["per_call_pre_estimate"]
    assert tiers["ceiling_large_tail"]["overspend_usd"] == pytest.approx(0.0, abs=1e-6)
    assert tiers["high_biased_1_25x_uniform"]["overspend_usd"] == pytest.approx(0.0, abs=1e-6)
    assert tiers["underestimate_0_6x_uniform"]["overspend_usd"] == pytest.approx(0.1, abs=1e-6)


@pytest.mark.unit
async def test_instrument_envelope_post_hoc_bound_is_per_caller() -> None:
    tiers = (await build_enforcement_ladder())["tiers"]["instrument_envelope_post_hoc"]
    assert tiers["serialized_two_callers"]["overspend_usd"] == pytest.approx(19.4, abs=1e-6)
    assert tiers["raced_two_callers"]["overspend_usd"] == pytest.approx(39.4, abs=1e-6)


@pytest.mark.unit
async def test_concurrency_defeats_the_pre_estimate_ceiling_bound() -> None:
    # The C2 headline: a perfect ceiling estimate (zero error) bounds a
    # serialized caller to zero overspend but leaves a raced pair over by one
    # full call. So "the estimate's error" is not the bound under concurrency.
    tiers = (await build_enforcement_ladder())["tiers"]["instrument_envelope_pre_estimate"]
    serialized = tiers["serialized_two_callers"]
    raced = tiers["raced_two_callers"]
    assert serialized["max_estimate_error_usd"] == pytest.approx(0.0, abs=1e-6)
    assert serialized["overspend_usd"] == pytest.approx(0.0, abs=1e-6)
    assert raced["max_estimate_error_usd"] == pytest.approx(0.0, abs=1e-6)
    assert raced["overspend_usd"] == pytest.approx(20.0, abs=1e-6)


# ---------- Property-based bounds over arbitrary traces ----------

_COSTS = st.lists(
    st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=60,
)


@pytest.mark.unit
@settings(max_examples=100, deadline=None)
@given(costs=_COSTS)
def test_property_serialized_ceiling_estimate_never_exceeds_ceiling(costs: list[float]) -> None:
    # A serialized caller under a ceiling estimate is admitted only when
    # spent + cost <= ceiling, so the ledger never exceeds the ceiling for
    # ANY trace: the pre-estimate tier is leak-free serialized.
    result = asyncio.run(_serial(costs, estimate=_ceiling))
    assert result["overspend_usd"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.unit
@settings(max_examples=100, deadline=None)
@given(costs=_COSTS)
def test_property_post_hoc_final_below_ceiling_plus_one_max_call(costs: list[float]) -> None:
    # Post-hoc admits while spent < ceiling, so the final ledger stays under
    # ceiling + one max call: the one-in-flight-call bound, over ANY trace.
    result = asyncio.run(_serial(costs, estimate=_post_hoc))
    max_call = result["max_call_usd"]
    if max_call > 0.0:
        assert result["final_spent_usd"] <= CAP_USD + max_call + 1e-6
    else:
        assert result["overspend_usd"] == pytest.approx(0.0, abs=1e-6)


if __name__ == "__main__":
    print(json.dumps(asyncio.run(build_enforcement_ladder()), indent=2))
