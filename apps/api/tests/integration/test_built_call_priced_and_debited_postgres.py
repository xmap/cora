"""Integration: a real built call, priced and debited over Postgres.

S4 (`test_mixed_source_envelope_postgres`) proves the envelope sums bought
and built spend source-blind, but it hand-constructs the built cost and
inserts it directly. This test closes the remaining link over the
production substrate: a real `LocalLLM` serves a call against a fake
OpenAI-compatible engine (no model), its returned token usage is priced by
the real `compute_cost_usd` at the local model's catalog rate, and that
computed cost lands in the real Postgres inference ledger and gates the
same envelope as a bought call. So serving -> pricing -> ledger -> gate
runs end to end over Postgres, with only the model faked.

The recorder's principal-binding and Decision-logbook provenance (the
`append_inferences` handler above the store) are a separate concern,
covered by the RunDebriefer subscriber integration tests; here the focus
is that a built call's genuinely-computed cost debits the real envelope.
"""

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest
from pytest_httpserver import HTTPServer

from cora.agent._budget_gate import find_allocation_breach
from cora.agent.adapters.local_llm import LocalLLM
from cora.agent.adapters.openai_compatible_backend import OpenAICompatibleBackend
from cora.decision.adapters import PostgresSpendLookup
from cora.decision.aggregates.decision import Inference
from cora.decision.aggregates.decision.entries import PostgresInferenceStore
from cora.infrastructure.observability.gen_ai import (
    ModelPricing,
    compute_cost_usd,
    set_pricing_overlay,
)
from cora.infrastructure.ports.allocation_lookup import AllocationLookupResult
from cora.infrastructure.ports.clock import SystemMonotonicClock
from cora.infrastructure.ports.llm import (
    LLMChatRequest,
    LLMContentBlock,
    LLMSystemPrompt,
    ModelRef,
)

_ACTIVATED_AT = datetime(2026, 7, 1, tzinfo=UTC)
_AS_OF = datetime(2026, 8, 1, tzinfo=UTC)
_IN_WINDOW = datetime(2026, 7, 10, tzinfo=UTC)
_LOCAL = ModelRef(provider="local", model="llama-3.3-70b")


class _FixedAllocationLookup:
    def __init__(self, *, ceiling_usd: float) -> None:
        self._result = AllocationLookupResult(
            allocation_id=uuid4(),
            ceiling_usd=ceiling_usd,
            activated_at=_ACTIVATED_AT,
            campaign_id=None,
        )

    async def find_active(self) -> AllocationLookupResult:
        return self._result


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="you are a helper"),)),
        user_message=LLMContentBlock(text="summarize the run"),
        structured_output_schema={"type": "object"},
        model_ref=_LOCAL,
    )


def _inference(*, provider: str, model: str, cost_usd: float) -> Inference:
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
        request_model=model,
        response_id=None,
        response_model=None,
        request_temperature=None,
        request_top_p=None,
        request_max_tokens=None,
        output_type=None,
        finish_reasons=(),
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cost_usd=cost_usd,
        agent_id=None,
        agent_name=None,
        agent_description=None,
        conversation_id=None,
        tool_name=None,
        tool_call_id=None,
        tool_type=None,
        messages=None,
    )


@pytest.mark.integration
async def test_a_built_call_is_priced_and_debits_the_envelope(
    db_pool: asyncpg.Pool, httpserver: HTTPServer
) -> None:
    # A fake local engine returns 1M input + 1M output tokens.
    httpserver.expect_request("/v1/chat/completions", method="POST").respond_with_json(
        {
            "model": "llama-3.3-70b",
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        }
    )
    # The local model's catalog rate: $0.02 / MTok in, $0.04 / MTok out.
    set_pricing_overlay(
        {
            (_LOCAL.provider, _LOCAL.model): ModelPricing(
                input_per_mtok=0.02,
                output_per_mtok=0.04,
                cache_write_per_mtok=0.02,
                cache_read_per_mtok=0.02,
            )
        }
    )
    try:
        adapter = LocalLLM(
            backend=OpenAICompatibleBackend(
                base_url=httpserver.url_for("/"),
                model="llama-3.3-70b",
            ),
            monotonic_clock=SystemMonotonicClock(),
        )

        response = await adapter.chat(_request())
        built_cost = compute_cost_usd(_LOCAL, response.usage)
        assert built_cost == pytest.approx(0.06)  # 1M*0.02 + 1M*0.04, from the served usage

        # The built call's real cost and a bought call land in one Postgres balance.
        await PostgresInferenceStore(db_pool).append(
            [
                _inference(provider="local", model="llama-3.3-70b", cost_usd=built_cost),
                _inference(provider="anthropic", model="claude-haiku-4-5", cost_usd=0.50),
            ]
        )
        spend_lookup = PostgresSpendLookup(db_pool)
        total = await spend_lookup.find_total_spend(
            window_start=_ACTIVATED_AT, window_end=_AS_OF
        )
        assert total.usd_spent == pytest.approx(0.56)  # 0.50 bought + 0.06 built

        # The built call's real cost is the amount that tips the envelope over.
        breach = await find_allocation_breach(
            allocation_lookup=_FixedAllocationLookup(ceiling_usd=0.55),
            spend_lookup=spend_lookup,
            as_of=_AS_OF,
        )
        assert breach is not None
        assert breach.spent_usd == pytest.approx(0.56)
    finally:
        set_pricing_overlay({})
