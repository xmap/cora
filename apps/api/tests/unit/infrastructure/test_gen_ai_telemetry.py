"""Unit tests for gen_ai telemetry helpers."""

# pyright: reportUnknownMemberType=false, reportPrivateUsage=false

import logging

import pytest
from opentelemetry import trace

from cora.infrastructure.observability.gen_ai import (
    PRICING,
    ModelPricing,
    _warned_missing_pricing,
    compute_cost_usd,
    estimate_llm_call_ceiling,
    record_llm_call,
    set_pricing_overlay,
)
from cora.infrastructure.ports.llm import LLMUsage, ModelRef


@pytest.fixture(autouse=True)
def reset_warning_set() -> None:
    """Each test starts with a clean warning-dedup set so
    test_unknown_model_logs_once_per_process can pin the
    single-warning behavior in isolation."""
    _warned_missing_pricing.clear()


@pytest.mark.unit
def test_compute_cost_for_known_model() -> None:
    """Opus 4.8 with 1M input tokens at $5/MT = exactly $5."""
    cost = compute_cost_usd(
        ModelRef(provider="anthropic", model="claude-opus-4-8"),
        LLMUsage(input_tokens=1_000_000, output_tokens=0),
    )
    assert cost == pytest.approx(5.00)


@pytest.mark.unit
def test_compute_cost_sums_all_four_token_types() -> None:
    """100k input + 50k output + 200k cache_create + 1M cache_read on Haiku 4.5:
    100k*$1 + 50k*$5 + 200k*$2 (1h-TTL write tier) + 1M*$0.10, per MTok."""
    cost = compute_cost_usd(
        ModelRef(provider="anthropic", model="claude-haiku-4-5"),
        LLMUsage(
            input_tokens=100_000,
            output_tokens=50_000,
            cache_creation_input_tokens=200_000,
            cache_read_input_tokens=1_000_000,
        ),
    )
    expected = 0.1 + 0.25 + 0.40 + 0.10
    assert cost == pytest.approx(expected)


@pytest.mark.unit
def test_unknown_model_returns_zero_and_logs_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    unknown = ModelRef(provider="anthropic", model="claude-imaginary-9-9")
    usage = LLMUsage(input_tokens=1_000_000, output_tokens=0)

    with caplog.at_level(logging.WARNING, logger="cora.infrastructure.observability.gen_ai"):
        cost1 = compute_cost_usd(unknown, usage)
        cost2 = compute_cost_usd(unknown, usage)

    assert cost1 == 0.0
    assert cost2 == 0.0
    matches = [r for r in caplog.records if "no PRICING entry" in r.getMessage()]
    assert len(matches) == 1, "warning must fire once per process per (provider, model)"


@pytest.mark.unit
def test_pricing_table_covers_all_documented_models() -> None:
    """Each model named in CORA's docs / design memos must have a
    PRICING entry, or compute_cost_usd silently returns $0 and
    cost dashboards lie. Add to PRICING when adding a model."""
    expected = {
        ("anthropic", "claude-opus-4-8"),
        ("anthropic", "claude-opus-4-7"),
        ("anthropic", "claude-sonnet-4-6"),
        ("anthropic", "claude-sonnet-4-5"),
        ("anthropic", "claude-haiku-4-5"),
    }
    assert expected.issubset(set(PRICING))


@pytest.mark.unit
def test_pricing_table_covers_every_fleet_default_model() -> None:
    """The fleet's ACTUAL default ModelRef constants must be priced,
    derived from the constants themselves so a default-model bump to
    an unpriced model fails here instead of silently metering $0.
    cost_usd is enforcement-load-bearing: an unpriced default makes
    the monthly USD gate permanently permissive."""
    from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL
    from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
    from cora.operation.adapters._llm_decide_prompt import DEFAULT_LLM_DECIDE_MODEL

    for default in (
        DEFAULT_RUN_DEBRIEF_MODEL,
        DEFAULT_CAUTION_DRAFTER_MODEL,
        DEFAULT_LLM_DECIDE_MODEL,
    ):
        key = (default.provider, default.model)
        assert key in PRICING, f"fleet default {key} has no PRICING entry"


@pytest.mark.unit
def test_record_llm_call_returns_cost_for_known_model() -> None:
    """Smoke test: with the no-op tracer (default in tests), every
    span op is a no-op but record_llm_call still computes cost."""
    span = trace.get_current_span()  # no-op span (no tracer configured)
    cost = record_llm_call(
        span,
        provider_name="anthropic",
        request_model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        response_model_id="claude-sonnet-4-6-20260301",
        usage=LLMUsage(input_tokens=1000, output_tokens=500),
        stop_reason="end_turn",
        max_tokens=1024,
    )
    expected = 0.003 + 0.0075
    assert cost == pytest.approx(expected)


@pytest.mark.unit
def test_record_llm_call_is_safe_with_noop_span() -> None:
    """No-op spans return INVALID context; set_attribute / histogram
    record must not raise. This is the production-test default
    (otel_exporter='none')."""
    span = trace.get_current_span()
    # Must not raise:
    cost = record_llm_call(
        span,
        provider_name="anthropic",
        request_model_ref=ModelRef(provider="anthropic", model="claude-haiku-4-5"),
        response_model_id="claude-haiku-4-5",
        usage=LLMUsage(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
        stop_reason="end_turn",
        max_tokens=512,
    )
    assert cost >= 0.0


@pytest.mark.unit
def test_model_pricing_is_frozen() -> None:
    """`ModelPricing` is a frozen dataclass: prevents accidental
    in-place edits to the PRICING table during a test run."""
    p = ModelPricing(
        input_per_mtok=1.0,
        output_per_mtok=2.0,
        cache_write_per_mtok=0.5,
        cache_read_per_mtok=0.1,
    )
    with pytest.raises((AttributeError, Exception)):
        p.input_per_mtok = 99.0  # type: ignore[misc]


@pytest.mark.unit
def test_estimate_llm_call_ceiling_prices_input_at_cache_write_rate() -> None:
    """The ceiling biases high on purpose: 300 chars -> 100 tokens (chars/3)
    at the cache-write rate, plus the full max_output_tokens at the output
    rate. Sonnet: cache write $6/M, output $15/M."""
    ceiling = estimate_llm_call_ceiling(
        ModelRef(provider="anthropic", model="claude-sonnet-4-5"),
        input_chars=300,
        max_output_tokens=1_000,
    )

    assert ceiling is not None
    assert ceiling.tokens == 100 + 1_000
    assert ceiling.cost_usd == pytest.approx(100 / 1e6 * 6.00 + 1_000 / 1e6 * 15.00)


@pytest.mark.unit
def test_estimate_llm_call_ceiling_unpriced_model_returns_none() -> None:
    """No price means no ceiling; the caller skips the gate (permissive),
    matching compute_cost_usd's zero-dollar posture for unpriced models."""
    ceiling = estimate_llm_call_ceiling(
        ModelRef(provider="acme", model="mystery-1"),
        input_chars=1_000,
        max_output_tokens=100,
    )

    assert ceiling is None


@pytest.mark.unit
def test_estimate_llm_call_ceiling_rounds_the_input_estimate_up() -> None:
    """301 chars is 100.33 tokens at chars/3; the ceiling must round UP
    (101), keeping the estimate's error one-sided."""
    ceiling = estimate_llm_call_ceiling(
        ModelRef(provider="anthropic", model="claude-sonnet-4-5"),
        input_chars=301,
        max_output_tokens=10,
    )

    assert ceiling is not None
    assert ceiling.tokens == 101 + 10


# Deliberately different from every static Sonnet figure so a test
# asserting these numbers proves the overlay was consulted.
_CATALOG_SONNET = ModelPricing(
    input_per_mtok=4.00,
    output_per_mtok=20.00,
    cache_write_per_mtok=8.00,
    cache_read_per_mtok=0.40,
)


@pytest.mark.unit
def test_catalog_overlay_entry_shadows_static_pricing_in_compute_cost_usd() -> None:
    """The catalog is the governance home of pricing: a catalog price
    for a statically priced identity wins over the table."""
    assert PRICING[("anthropic", "claude-sonnet-4-5")] != _CATALOG_SONNET
    set_pricing_overlay({("anthropic", "claude-sonnet-4-5"): _CATALOG_SONNET})
    try:
        cost = compute_cost_usd(
            ModelRef(provider="anthropic", model="claude-sonnet-4-5"),
            LLMUsage(input_tokens=1_000_000, output_tokens=0),
        )
        assert cost == pytest.approx(4.00)
    finally:
        set_pricing_overlay({})


@pytest.mark.unit
def test_catalog_overlay_entry_shadows_static_pricing_in_estimate_ceiling() -> None:
    """The pre-estimate gate must meter the same governed price the
    post-call cost meter uses, or the gate and the bill disagree."""
    set_pricing_overlay({("anthropic", "claude-sonnet-4-5"): _CATALOG_SONNET})
    try:
        ceiling = estimate_llm_call_ceiling(
            ModelRef(provider="anthropic", model="claude-sonnet-4-5"),
            input_chars=300,
            max_output_tokens=1_000,
        )
        assert ceiling is not None
        assert ceiling.cost_usd == pytest.approx(100 / 1e6 * 8.00 + 1_000 / 1e6 * 20.00)
    finally:
        set_pricing_overlay({})


@pytest.mark.unit
def test_key_absent_from_overlay_falls_back_to_static_pricing() -> None:
    """An installed overlay only shadows its own keys; every other
    identity keeps its static-table price."""
    set_pricing_overlay({("anthropic", "claude-sonnet-4-5"): _CATALOG_SONNET})
    try:
        cost = compute_cost_usd(
            ModelRef(provider="anthropic", model="claude-opus-4-8"),
            LLMUsage(input_tokens=1_000_000, output_tokens=0),
        )
        assert cost == pytest.approx(5.00)
    finally:
        set_pricing_overlay({})


@pytest.mark.unit
def test_replacing_overlay_with_empty_mapping_restores_static_only_pricing() -> None:
    """Wholesale replacement is the removal path: an entry absent from
    the new mapping falls back to the static table on the next set."""
    set_pricing_overlay({("anthropic", "claude-sonnet-4-5"): _CATALOG_SONNET})
    try:
        set_pricing_overlay({})
        cost = compute_cost_usd(
            ModelRef(provider="anthropic", model="claude-sonnet-4-5"),
            LLMUsage(input_tokens=1_000_000, output_tokens=0),
        )
        assert cost == pytest.approx(3.00)
    finally:
        set_pricing_overlay({})


@pytest.mark.unit
def test_key_missing_from_both_overlay_and_static_still_warns_and_costs_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The unpriced-model warning fires only when BOTH the overlay and
    the static table miss; an overlay being installed must not mute it."""
    set_pricing_overlay({("anthropic", "claude-sonnet-4-5"): _CATALOG_SONNET})
    try:
        with caplog.at_level(logging.WARNING, logger="cora.infrastructure.observability.gen_ai"):
            cost = compute_cost_usd(
                ModelRef(provider="acme", model="mystery-1"),
                LLMUsage(input_tokens=1_000_000, output_tokens=0),
            )
        assert cost == 0.0
        matches = [r for r in caplog.records if "no PRICING entry" in r.getMessage()]
        assert len(matches) == 1
    finally:
        set_pricing_overlay({})
