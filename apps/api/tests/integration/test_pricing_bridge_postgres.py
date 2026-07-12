"""Integration test for `refresh_language_model_pricing` over Postgres.

Seeds two Approved catalog entries via direct event appends (pricing
has one home, the aggregate; the projection deliberately carries no
rates) plus matching projection rows (the read model's only
production writer is the projection worker, mirroring
test_language_model_lookup_postgres.py's INSERT scaffolding), then
verifies the bridge installs the TokenPricing entry's CATALOG figures
into the observability overlay and skips the GpuHourPricing entry
(per-token math only; GPU-hour rates feed the future allocation arc).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent._pricing_bridge import refresh_language_model_pricing
from cora.agent.aggregates.language_model import (
    CostBasis,
    GpuHourPricing,
    LanguageModelApproved,
    LanguageModelDefined,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    to_payload,
)
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.observability import gen_ai
from cora.infrastructure.observability.gen_ai import (
    PRICING,
    compute_cost_usd,
    set_pricing_overlay,
)
from cora.infrastructure.ports.llm import LLMUsage, ModelRef

_TOKEN_PROVIDER = "anthropic"
_TOKEN_MODEL = "claude-sonnet-4-5"
_GPU_PROVIDER = "facility"
_GPU_MODEL = "held-weights-70b"

_T1 = datetime(2026, 7, 10, tzinfo=UTC)

# Deliberately different from the static PRICING row for the same
# identity, so the cost assertion proves the CATALOG figures won.
_CATALOG_TOKEN_PRICING = TokenPricing(
    input_per_mtok=4.00,
    output_per_mtok=20.00,
    cache_write_per_mtok=8.00,
    cache_read_per_mtok=0.40,
)

_INSERT_PROJECTION_SQL = """
INSERT INTO proj_agent_language_model_summary
    (language_model_id, name, provider, model, snapshot_pin, served_via,
     data_tier, archivability, status, created_at)
VALUES ($1, $2, $3, $4, NULL, 'Direct', 'Internal', 'Alias', 'Approved', $5)
"""


async def _seed_approved_entry(
    pool: asyncpg.Pool,
    store: PostgresEventStore,
    *,
    language_model_id: UUID,
    name: str,
    provider: str,
    model: str,
    cost_basis: CostBasis,
) -> None:
    defined_event = LanguageModelDefined(
        language_model_id=language_model_id,
        name=name,
        provider=provider,
        model=model,
        snapshot_pin=None,
        served_via="Direct",
        endpoint_note=None,
        cost_basis=cost_basis_to_payload(cost_basis),
        data_tier="Internal",
        archivability="Alias",
        occurred_at=_T1,
    )
    approved_event = LanguageModelApproved(
        language_model_id=language_model_id,
        occurred_at=_T1,
    )
    await store.append(
        stream_type="LanguageModel",
        stream_id=language_model_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_T1,
                event_id=uuid4(),
                command_name="DefineLanguageModel",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
            for event in (defined_event, approved_event)
        ],
    )
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_PROJECTION_SQL,
            language_model_id,
            name,
            provider,
            model,
            _T1,
        )


@pytest.mark.integration
async def test_bridge_installs_catalog_token_pricing_and_skips_gpu_hour_entry(
    db_pool: asyncpg.Pool,
) -> None:
    """One Approved TokenPricing entry lands in the overlay with the
    CATALOG figures (shadowing the static row for the same identity);
    the Approved GpuHourPricing entry is skipped entirely."""
    store = PostgresEventStore(db_pool)
    await _seed_approved_entry(
        db_pool,
        store,
        language_model_id=uuid4(),
        name="Claude Sonnet 4.5 (facility rates)",
        provider=_TOKEN_PROVIDER,
        model=_TOKEN_MODEL,
        cost_basis=_CATALOG_TOKEN_PRICING,
    )
    await _seed_approved_entry(
        db_pool,
        store,
        language_model_id=uuid4(),
        name="Facility held-weights pool",
        provider=_GPU_PROVIDER,
        model=_GPU_MODEL,
        cost_basis=GpuHourPricing(usd_per_gpu_hour=12.50),
    )

    try:
        installed = await refresh_language_model_pricing(pool=db_pool, event_store=store)

        assert installed == 1
        assert set(gen_ai._pricing_overlay) == {(_TOKEN_PROVIDER, _TOKEN_MODEL)}

        static_row = PRICING[(_TOKEN_PROVIDER, _TOKEN_MODEL)]
        assert static_row.input_per_mtok != _CATALOG_TOKEN_PRICING.input_per_mtok
        cost = compute_cost_usd(
            ModelRef(provider=_TOKEN_PROVIDER, model=_TOKEN_MODEL),
            LLMUsage(input_tokens=1_000_000, output_tokens=0),
        )
        assert cost == pytest.approx(_CATALOG_TOKEN_PRICING.input_per_mtok)
    finally:
        set_pricing_overlay({})
