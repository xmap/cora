"""Overspend characterization of the two shipped enforcement-ladder tiers.

Measures the quantity the facility-LLM-budget paper's enforcement-ladder
table asserts: how much a caller can overspend a cap under each tier that
is actually built in CORA. It drives the REAL gate entry points
(`find_budget_breach` for the coarse post-hoc tier, `BudgetSpendGuard`
for the per-call pre-estimate tier) over synthetic cost traces, against an
accumulating in-memory ledger, and reports the overspend each leaks. When
`CORA_PERF_OUT` is set it writes the result as JSON (the paper's
`data/enforcement_ladder.json`); otherwise it just asserts the bounds hold.

Pure in-memory: `InMemoryEventStore` plus a mutable ledger `SpendLookup`,
no Postgres, no wall clock (gating is by event time, `_NOW`), so the run is
deterministic. Only the shipped tiers are measured; the alert-only tier is not
a control and the leak-free reserve-post-void tier is not yet built (both are
analytical rows in the paper's table).

The envelope arm models the worst case rather than an incidence rate: it drives
the callers so that each reaches the post-hoc arm before any has posted. That
alignment is what the shipped wiring permits, not what it guarantees on every
Run, so the figure bounds the race, it does not predict how often it happens.

The three claims under test:
  - Coarse post-hoc debits after each call and refuses the next once the
    cap is reached, so the one call that crosses the cap still completes:
    overspend is bounded by one in-flight call's cost, and reaches nearly a
    whole large call when that call arrives with the balance near zero.
  - Per-call pre-estimate refuses when recorded spend plus the call's
    estimated ceiling would exceed the cap, so a true ceiling estimate
    yields zero overspend, and an under-estimate leaks at most that one
    call's estimate error.
  - That "one in-flight call" bound is per CALLER, not per envelope. Against
    the shared instrument-wide allocation, every caller that reaches the
    post-hoc arm before any of them posts leaks a call of its own, so the two
    LLM subscribers that fire on the same terminal Run double the bound. This
    is the residual the unbuilt reserve-post-void tier owns.
"""

# pyright: reportPrivateUsage=false

import asyncio
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent._budget_gate import find_allocation_breach, find_budget_breach
from cora.agent.adapters import BudgetSpendGuard
from cora.agent.aggregates.agent import load_agent
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from cora.infrastructure.ports.spend_lookup import SpendLookupResult, TotalSpendResult
from tests.unit.agent._helpers import FakeAllocationLookup, seed_versioned_agent

_NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
_ENVELOPE_ACTIVATED_AT = datetime(2026, 7, 1, 8, 0, 0, tzinfo=UTC)

_CAP_USD = 100.0
_SMALL_CALL_USD = 0.70
_LARGE_CALL_USD = 20.0
_NEAR_FULL_USD = 99.40
_EPS = 1e-9


class _LedgerSpendLookup:
    """Accumulating `SpendLookup`: the spend ledger the seam posts to.

    Every permitted call adds its actual cost, and every gate check reads
    the current running sum, exactly as the post-hoc gate and the
    pre-estimate guard query recorded spend between calls in production.
    """

    def __init__(self) -> None:
        self.usd_spent = 0.0
        self.tokens_spent = 0
        self.call_count = 0

    async def find_agent_spend(
        self, *, agent_id: UUID, window_start: datetime, window_end: datetime
    ) -> SpendLookupResult:
        return SpendLookupResult(
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
            usd_spent=self.usd_spent,
            tokens_spent=self.tokens_spent,
            call_count=self.call_count,
        )

    async def find_total_spend(
        self, *, window_start: datetime, window_end: datetime
    ) -> TotalSpendResult:
        return TotalSpendResult(
            window_start=window_start,
            window_end=window_end,
            usd_spent=self.usd_spent,
            call_count=self.call_count,
        )


@dataclass(frozen=True)
class _Measurement:
    """One tier's run over a cost trace: what it permitted and overspent."""

    permitted_calls: int
    offered_calls: int
    final_spent_usd: float
    overspend_usd: float
    unused_headroom_usd: float
    max_call_usd: float
    max_estimate_error_usd: float | None = None

    def to_json(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _measure(
    cap_usd: float,
    costs: Sequence[float],
    permitted: int,
    spent: float,
    *,
    max_estimate_error: float | None = None,
) -> _Measurement:
    return _Measurement(
        permitted_calls=permitted,
        offered_calls=len(costs),
        final_spent_usd=round(spent, 6),
        overspend_usd=round(max(0.0, spent - cap_usd), 6),
        unused_headroom_usd=round(max(0.0, cap_usd - spent), 6),
        max_call_usd=round(max(costs), 6),
        max_estimate_error_usd=(
            None if max_estimate_error is None else round(max(0.0, max_estimate_error), 6)
        ),
    )


async def _versioned_capped_agent(cap_usd: float) -> tuple[InMemoryEventStore, UUID]:
    """A Versioned agent carrying a single monthly USD cap."""
    store = InMemoryEventStore()
    agent_id = uuid4()
    await seed_versioned_agent(
        store,
        agent_id=agent_id,
        genesis_event_id=uuid4(),
        version_event_id=uuid4(),
        correlation_id=uuid4(),
        principal_id=uuid4(),
        defined_at=_NOW,
        versioned_at=_NOW,
        monthly_usd_cap=cap_usd,
    )
    return store, agent_id


async def _drive_post_hoc(cap_usd: float, costs: Sequence[float]) -> _Measurement:
    """Coarse post-hoc: check recorded spend, permit, then post the actual cost."""
    store, agent_id = await _versioned_capped_agent(cap_usd)
    agent = await load_agent(store, agent_id)
    ledger = _LedgerSpendLookup()
    permitted = 0
    for cost in costs:
        breach = await find_budget_breach(agent=agent, spend_lookup=ledger, as_of=_NOW)
        if breach is not None:
            break
        ledger.usd_spent += cost
        permitted += 1
    return _measure(cap_usd, costs, permitted, ledger.usd_spent)


async def _drive_pre_estimate(
    cap_usd: float, costs: Sequence[float], estimates: Sequence[float]
) -> _Measurement:
    """Per-call pre-estimate: refuse when recorded spend plus the estimate would breach."""
    store, agent_id = await _versioned_capped_agent(cap_usd)
    ledger = _LedgerSpendLookup()
    guard = BudgetSpendGuard(event_store=store, spend_lookup=ledger)
    permitted = 0
    max_estimate_error = 0.0
    for cost, estimate in zip(costs, estimates, strict=True):
        reason = await guard.refusal_reason(
            agent_id=agent_id, estimated_cost_usd=estimate, estimated_tokens=0, as_of=_NOW
        )
        if reason is not None:
            break
        ledger.usd_spent += cost
        permitted += 1
        max_estimate_error = max(max_estimate_error, cost - estimate)
    return _measure(
        cap_usd, costs, permitted, ledger.usd_spent, max_estimate_error=max_estimate_error
    )


async def _drive_envelope_race(
    ceiling_usd: float,
    prefill_usd: float,
    costs: Sequence[float],
    *,
    concurrent: bool,
) -> _Measurement:
    """Drive several callers against one shared instrument-wide envelope.

    `concurrent=True` models the shipped wiring: the projection worker runs one
    task per subscriber, and the LLM subscribers fire on the same terminal Run
    events, so each can reach the envelope's post-hoc arm (`pending_usd` of 0)
    before any of them has posted its cost. `concurrent=False` serializes the
    same callers as the control. The contrast is the measurement: the post-hoc
    arm's "one in-flight call" bound holds per caller, not per envelope.
    """
    ledger = _LedgerSpendLookup()
    ledger.usd_spent = prefill_usd
    lookup = FakeAllocationLookup(
        AllocationLookupResult(
            allocation_id=uuid4(),
            ceiling_usd=ceiling_usd,
            activated_at=_ENVELOPE_ACTIVATED_AT,
            campaign_id=None,
        )
    )

    async def _admit(cost: float) -> float:
        breach = await find_allocation_breach(
            allocation_lookup=lookup, spend_lookup=ledger, as_of=_NOW
        )
        return 0.0 if breach is not None else cost

    permitted = 0
    if concurrent:
        admitted = await asyncio.gather(*[_admit(cost) for cost in costs])
        for cost in admitted:
            if cost > 0.0:
                ledger.usd_spent += cost
                permitted += 1
    else:
        for cost in costs:
            admitted_cost = await _admit(cost)
            if admitted_cost == 0.0:
                break
            ledger.usd_spent += admitted_cost
            permitted += 1

    return _measure(ceiling_usd, costs, permitted, ledger.usd_spent)


def _write_perf_json(path: str, result: Mapping[str, object]) -> None:
    """Sync JSON write, kept off the async test body (ASYNC230)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


@pytest.mark.unit
async def test_enforcement_ladder_overspend_matches_the_declared_bounds() -> None:
    # A uniform stream of small calls, and the same stream with one large
    # call arriving while the balance is nearly full (the worst case for a
    # post-hoc gate: the crossing call is large).
    uniform = [_SMALL_CALL_USD] * 200
    fill_to_near_cap = math.floor(_CAP_USD / _SMALL_CALL_USD)
    large_tail = [_SMALL_CALL_USD] * fill_to_near_cap + [_LARGE_CALL_USD] + [_SMALL_CALL_USD] * 5

    post_hoc_uniform = await _drive_post_hoc(_CAP_USD, uniform)
    post_hoc_large_tail = await _drive_post_hoc(_CAP_USD, large_tail)

    # Pre-estimate with a true ceiling (estimate == actual) on the same
    # worst-case trace; an under-estimate (0.6 of cost) and a high-biased
    # ceiling (1.25 of cost, the production posture) on the uniform trace.
    ceiling_large_tail = await _drive_pre_estimate(_CAP_USD, large_tail, large_tail)
    underestimate_uniform = await _drive_pre_estimate(_CAP_USD, uniform, [0.6 * c for c in uniform])
    high_biased_uniform = await _drive_pre_estimate(_CAP_USD, uniform, [1.25 * c for c in uniform])

    # Two callers against one shared instrument envelope: the shipped pair, since
    # RunDebriefer and CautionDrafter fire on the same terminal Run events and the
    # projection worker runs one task per subscriber. Serialized is the control.
    envelope_serialized = await _drive_envelope_race(
        _CAP_USD, _NEAR_FULL_USD, [_LARGE_CALL_USD] * 2, concurrent=False
    )
    envelope_raced = await _drive_envelope_race(
        _CAP_USD, _NEAR_FULL_USD, [_LARGE_CALL_USD] * 2, concurrent=True
    )

    result = {
        "environment": (
            "in-memory: InMemoryEventStore + accumulating ledger SpendLookup; "
            "deterministic, event-time gating (no wall clock)"
        ),
        "cap_usd": _CAP_USD,
        "small_call_usd": _SMALL_CALL_USD,
        "large_call_usd": _LARGE_CALL_USD,
        "tiers": {
            "coarse_post_hoc": {
                "bound": "one in-flight call per caller",
                "uniform": post_hoc_uniform.to_json(),
                "large_tail": post_hoc_large_tail.to_json(),
            },
            "per_call_pre_estimate": {
                "bound": "the estimate's error (zero when the estimate is a ceiling)",
                "ceiling_large_tail": ceiling_large_tail.to_json(),
                "underestimate_0_6x_uniform": underestimate_uniform.to_json(),
                "high_biased_1_25x_uniform": high_biased_uniform.to_json(),
            },
            "instrument_envelope_post_hoc": {
                "bound": "one in-flight call per CALLER, not per envelope",
                "serialized_two_callers": envelope_serialized.to_json(),
                "raced_two_callers": envelope_raced.to_json(),
            },
        },
    }

    out = os.environ.get("CORA_PERF_OUT")
    if out:
        _write_perf_json(out, result)
    print("\nENFORCEMENT_LADDER_PERF " + json.dumps(result))

    # Coarse post-hoc leaks at most one in-flight call, and the worst-case
    # trace shows that leak is nearly a whole large call.
    assert 0.0 <= post_hoc_uniform.overspend_usd <= _SMALL_CALL_USD + _EPS
    assert 0.0 < post_hoc_large_tail.overspend_usd <= _LARGE_CALL_USD + _EPS
    assert post_hoc_large_tail.overspend_usd >= _LARGE_CALL_USD - _SMALL_CALL_USD

    # Per-call pre-estimate with a ceiling estimate never overspends; an
    # under-estimate leaks at most that one call's estimate error; a
    # high-biased ceiling trades a little unused headroom for zero overspend.
    assert ceiling_large_tail.overspend_usd == 0.0
    assert (
        underestimate_uniform.overspend_usd
        <= (underestimate_uniform.max_estimate_error_usd or 0.0) + _EPS
    )
    assert high_biased_uniform.overspend_usd == 0.0
    assert high_biased_uniform.unused_headroom_usd > 0.0

    # The shared envelope's post-hoc arm bounds overspend to one in-flight call
    # per CALLER, not per envelope: serializing the pair leaks one call, racing
    # them leaks one per caller. That gap is the residual the reserve-post-void
    # tier owns, and it is the shipped wiring rather than a hypothetical.
    assert envelope_serialized.permitted_calls == 1
    assert 0.0 < envelope_serialized.overspend_usd <= _LARGE_CALL_USD + _EPS
    assert envelope_raced.permitted_calls == 2
    assert envelope_raced.overspend_usd > envelope_serialized.overspend_usd
    assert envelope_raced.overspend_usd <= 2 * _LARGE_CALL_USD + _EPS
