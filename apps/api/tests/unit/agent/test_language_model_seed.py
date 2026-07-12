"""Unit tests for the fleet-default LanguageModel catalog seed.

Pins the consistency contract: every model the shipped fleet declares
(RunDebriefer, CautionDrafter, and the ExperimentSteerer LLM-decide
default, whose identity the seed mirrors as literals across the tach
boundary) has a seeded catalog entry, born Approved, at a
deterministic id, with pricing figures matching the observability
PRICING table. Idempotency mirrors test_caution_drafter_seed.py.
"""

from datetime import UTC, datetime

import pytest

from cora.agent.aggregates.language_model import (
    LanguageModelStatus,
    TokenPricing,
    load_language_model,
)
from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
from cora.agent.seed_language_models import (
    SEED_LANGUAGE_MODELS,
    language_model_seed_id,
    seed_language_models,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability.gen_ai import PRICING
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.operation.adapters._llm_decide_prompt import DEFAULT_LLM_DECIDE_MODEL

_FLEET_DEFAULTS = (
    DEFAULT_RUN_DEBRIEF_MODEL,
    DEFAULT_CAUTION_DRAFTER_MODEL,
    DEFAULT_LLM_DECIDE_MODEL,
)


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 7, 12, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
def test_fleet_default_model_refs_each_match_a_seeded_entry() -> None:
    """Every fleet default (provider, model) has a seed entry, so a
    fresh deployment's define_agent gate never refuses the shipped
    fleet. Compares BOTH sides by import, including the LLM-decide
    default the seed mirrors as literals across the tach boundary."""
    seeded_identities = {
        (entry.model_ref.provider, entry.model_ref.model) for entry in SEED_LANGUAGE_MODELS
    }
    for fleet_default in _FLEET_DEFAULTS:
        assert (fleet_default.provider, fleet_default.model) in seeded_identities


@pytest.mark.unit
def test_seed_pricing_figures_match_observability_pricing_table() -> None:
    """The seed copies PRICING numbers as literals; this pin catches a
    repricing that forgets the catalog side (or vice versa)."""
    for entry in SEED_LANGUAGE_MODELS:
        pricing = PRICING[(entry.model_ref.provider, entry.model_ref.model)]
        assert entry.cost_basis == TokenPricing(
            input_per_mtok=pricing.input_per_mtok,
            output_per_mtok=pricing.output_per_mtok,
            cache_write_per_mtok=pricing.cache_write_per_mtok,
            cache_read_per_mtok=pricing.cache_read_per_mtok,
        )


@pytest.mark.unit
async def test_seed_creates_each_entry_born_approved_at_deterministic_id() -> None:
    """Two events per stream (Defined + Approved) fold to Approved:
    seeds bypass the handlers, and the shipped fleet must be usable
    from first boot."""
    kernel = _kernel()
    await seed_language_models(kernel)

    for entry in SEED_LANGUAGE_MODELS:
        language_model_id = language_model_seed_id(entry.model_ref.provider, entry.model_ref.model)
        state = await load_language_model(kernel.event_store, language_model_id)
        assert state is not None
        assert state.id == language_model_id
        assert state.status == LanguageModelStatus.APPROVED
        assert state.model_ref.provider == entry.model_ref.provider
        assert state.model_ref.model == entry.model_ref.model
        assert state.cost_basis == entry.cost_basis


@pytest.mark.unit
async def test_seed_is_idempotent() -> None:
    """Re-running the seed is a no-op (ConcurrencyError-as-success
    pattern); streams keep exactly the two genesis events."""
    kernel = _kernel()
    await seed_language_models(kernel)
    # Should not raise on second run.
    await seed_language_models(kernel)

    for entry in SEED_LANGUAGE_MODELS:
        language_model_id = language_model_seed_id(entry.model_ref.provider, entry.model_ref.model)
        events, version = await kernel.event_store.load("LanguageModel", language_model_id)
        assert version == 2
        assert [e.event_type for e in events] == [
            "LanguageModelDefined",
            "LanguageModelApproved",
        ]
