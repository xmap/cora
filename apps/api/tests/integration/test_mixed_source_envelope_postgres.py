"""Integration demonstration: one budget envelope over buy AND build.

The paper's headline claim is that a single per-beamline allocation
envelope covers LLM spend whether a call was BOUGHT from an external
provider (token-billed) or BUILT on a facility GPU (the in-house path).
The enforcement seam makes this true by construction: `find_total_spend`
sums `cost_usd` over every inference row regardless of `provider_name`,
and `find_allocation_breach` gates on that source-blind total.

These tests exercise the real store (`PostgresInferenceStore`, the store
the subscribers' recorder ultimately writes to), the real sum
(`PostgresSpendLookup`), and the real gate (`find_allocation_breach`) over
rows from both sources. The Active envelope is a fixed test double here (a
ceiling plus a window start); the allocation projection read is covered in
`test_allocation_lookup_postgres`.

What is demonstrated: bought and built spend land in one balance and halt
on the combined total, and a metered-free built call (cost_usd 0) is
recorded yet adds nothing to the debit. What is NOT: these record rows
directly, so they do not exercise the subscriber recorder or the
principal-bound `append_inferences` handler, nor the build serving-and-
pricing path (`LocalLLM.chat` to usage to `compute_cost_usd` to recorder);
those are exercised by the adapter, meter, and approval-guard unit tests.
The one-budget-over-buy-and-build guarantee rests on TWO mechanisms: this
source-blind sum, AND the approval guard that blocks a GPU-hour-priced
(silently $0) built model (`test_approve_language_model_decider`). The
built path's real GPU cost is metered separately as the
`cora.agent.llm.gpu.shadow_cost.usd` observability signal (never a debit);
it does not appear in this ledger.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent._budget_gate import find_allocation_breach
from cora.decision.adapters import PostgresSpendLookup
from cora.decision.aggregates.decision import Inference
from cora.decision.aggregates.decision.entries import PostgresInferenceStore
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult

_ACTIVATED_AT = datetime(2026, 7, 1, tzinfo=UTC)
_AS_OF = datetime(2026, 8, 1, tzinfo=UTC)
_IN_WINDOW = datetime(2026, 7, 10, tzinfo=UTC)

_BOUGHT = "anthropic"  # an external, token-billed provider
_BUILT = "local"  # the facility-hosted (in-house) serving path


class _FixedAllocationLookup:
    """Test double: one fixed Active envelope for the window under test."""

    def __init__(self, *, ceiling_usd: float) -> None:
        self._result = AllocationLookupResult(
            allocation_id=uuid4(),
            ceiling_usd=ceiling_usd,
            activated_at=_ACTIVATED_AT,
            campaign_id=None,
        )

    async def find_active(self) -> AllocationLookupResult:
        return self._result


def _inference(*, provider: str, cost_usd: float, agent_id: UUID | None = None) -> Inference:
    return Inference(
        event_id=uuid4(),
        decision_id=uuid4(),
        logbook_id=uuid4(),
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_IN_WINDOW,
        duration=None,
        operation_name="chat",
        provider_name=provider,
        request_model="llama-3.3-70b" if provider == _BUILT else "claude-haiku-4-5",
        response_id=None,
        response_model=None,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=100,
        output_tokens=50,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
        cost_usd=cost_usd,
        agent_id=str(agent_id) if agent_id is not None else None,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )


@pytest.mark.integration
async def test_one_envelope_sums_bought_and_built_spend(db_pool: asyncpg.Pool) -> None:
    """Bought and built rows land in one balance; below the ceiling the gate permits."""
    await PostgresInferenceStore(db_pool).append(
        [
            _inference(provider=_BOUGHT, cost_usd=0.40),
            _inference(provider=_BUILT, cost_usd=0.30),
        ]
    )
    spend_lookup = PostgresSpendLookup(db_pool)

    total = await spend_lookup.find_total_spend(window_start=_ACTIVATED_AT, window_end=_AS_OF)
    assert total.usd_spent == pytest.approx(0.70)  # 0.40 bought + 0.30 built, one balance
    assert total.call_count == 2

    breach = await find_allocation_breach(
        allocation_lookup=_FixedAllocationLookup(ceiling_usd=1.00),
        spend_lookup=spend_lookup,
        as_of=_AS_OF,
    )
    assert breach is None  # 0.70 < 1.00


@pytest.mark.integration
async def test_envelope_halts_on_the_combined_bought_and_built_total(
    db_pool: asyncpg.Pool,
) -> None:
    """Neither source alone crosses the ceiling, but their combined total does:
    the halt fires on the sum, which is the one-budget-over-buy-and-build claim."""
    await PostgresInferenceStore(db_pool).append(
        [
            _inference(provider=_BOUGHT, cost_usd=0.60),
            _inference(provider=_BUILT, cost_usd=0.50),
        ]
    )

    breach = await find_allocation_breach(
        allocation_lookup=_FixedAllocationLookup(ceiling_usd=1.00),
        spend_lookup=PostgresSpendLookup(db_pool),
        as_of=_AS_OF,
    )

    assert breach is not None  # 0.60 + 0.50 = 1.10 >= 1.00, neither alone would
    assert breach.spent_usd == pytest.approx(1.10)
    assert breach.ceiling_usd == pytest.approx(1.00)


@pytest.mark.integration
async def test_metered_free_built_calls_are_recorded_but_add_nothing(
    db_pool: asyncpg.Pool,
) -> None:
    """A metered-free built model prices at cost_usd 0: its calls count and are
    audited, but they do not move the balance, which is the default policy."""
    await PostgresInferenceStore(db_pool).append(
        [
            _inference(provider=_BOUGHT, cost_usd=0.40),
            _inference(provider=_BUILT, cost_usd=0.0),
            _inference(provider=_BUILT, cost_usd=0.0),
            _inference(provider=_BUILT, cost_usd=0.0),
        ]
    )

    total = await PostgresSpendLookup(db_pool).find_total_spend(
        window_start=_ACTIVATED_AT, window_end=_AS_OF
    )
    assert total.usd_spent == pytest.approx(0.40)  # only the bought call debits
    assert total.call_count == 4  # the three metered-free built calls are still recorded


@pytest.mark.integration
async def test_pre_estimate_arm_halts_the_next_call_before_it_breaches(
    db_pool: asyncpg.Pool,
) -> None:
    """The pre-estimate arm refuses the next call when spend plus its estimate
    would cross the ceiling, even though recorded spend is still under it. This
    is the arm a live built call uses; under genuine concurrency several
    in-flight calls race this gate and overspend is bounded per caller, not a
    clean cutoff, the concurrent pre-estimate overspend the enforcement ladder
    characterizes separately. This test stays single-threaded and shows only the
    arithmetic, not the race."""
    await PostgresInferenceStore(db_pool).append(
        [
            _inference(provider=_BOUGHT, cost_usd=0.60),
            _inference(provider=_BUILT, cost_usd=0.30),
        ]
    )
    allocation_lookup = _FixedAllocationLookup(ceiling_usd=1.00)
    spend_lookup = PostgresSpendLookup(db_pool)

    # Recorded 0.90 < 1.00: the post-hoc arm alone would still permit.
    post_hoc = await find_allocation_breach(
        allocation_lookup=allocation_lookup, spend_lookup=spend_lookup, as_of=_AS_OF
    )
    assert post_hoc is None

    # But the next call's 0.20 estimate would carry the total to 1.10 > 1.00.
    projected = await find_allocation_breach(
        allocation_lookup=allocation_lookup,
        spend_lookup=spend_lookup,
        as_of=_AS_OF,
        pending_usd=0.20,
    )
    assert projected is not None
    assert projected.spent_usd == pytest.approx(0.90)
