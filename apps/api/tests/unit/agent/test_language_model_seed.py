"""Unit tests for the LanguageModel catalog seed.

Pins two consistency contracts. First, every model the shipped fleet
declares (RunDebriefer, CautionDrafter, and the ExperimentSteerer
LLM-decide default, whose identity the seed mirrors as literals across
the tach boundary) has a seeded catalog entry, born Approved, at a
deterministic id, with pricing figures matching the observability
PRICING table. Second, the two catalog-only entries for the 2-BM
buy-vs-build debrief comparison (Argo Haiku 4.5, the in-house
placeholder) are priced and served under the right route, and the
in-house entry deliberately has no PRICING counterpart. Idempotency
mirrors test_caution_drafter_seed.py.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog.testing

from cora.agent._pricing_bridge import to_model_pricing
from cora.agent.adapters.argo_llm import ARGO_PROVIDER_NAME
from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    LanguageModelDefined,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
    cost_basis_to_payload,
    event_type_name,
    load_language_model,
    to_payload,
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
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability.gen_ai import PRICING
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from cora.operation.adapters._llm_decide_prompt import DEFAULT_LLM_DECIDE_MODEL

_FLEET_DEFAULTS = (
    DEFAULT_RUN_DEBRIEF_MODEL,
    DEFAULT_CAUTION_DRAFTER_MODEL,
    DEFAULT_LLM_DECIDE_MODEL,
)

# The in-house entry has no PRICING counterpart by design (its rate is
# catalog-only); the Argo entry DOES mirror a PRICING row, same as the
# three fleet defaults. Pricing-drift tests below scope to entries
# PRICING actually prices.
_LOCAL_PROVIDER_NAME = "local"


def _kernel() -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 7, 12, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
    )


@pytest.mark.unit
def test_fleet_default_model_refs_each_equal_their_seeded_entry() -> None:
    """Every fleet default resolves to a seed entry whose full ModelRef
    (provider, model, AND snapshot_pin) equals the fleet constant, so a
    fresh deployment's define_agent gate never refuses the shipped
    fleet and a snapshot-pin drift on either side fails here. Compares
    BOTH sides by import, including the LLM-decide default the seed
    mirrors as literals across the tach boundary.

    The identity-set relationship is a SUBSET, not an equality: two
    further seed entries (Argo Haiku 4.5, the 2-BM in-house
    placeholder) are catalog-only and declared by no fleet agent as
    its compile-time default (see test_two_buy_vs_build_entries_are_
    catalog_only_not_fleet_defaults below), so the seeded set is
    strictly larger. Every fleet default still resolving to a seed
    entry is what this subset check pins; no fleet default is
    orphaned."""
    seeded_by_identity = {
        (entry.model_ref.provider, entry.model_ref.model): entry.model_ref
        for entry in SEED_LANGUAGE_MODELS
    }
    assert {
        (fleet_default.provider, fleet_default.model) for fleet_default in _FLEET_DEFAULTS
    } <= set(seeded_by_identity)
    for fleet_default in _FLEET_DEFAULTS:
        assert seeded_by_identity[(fleet_default.provider, fleet_default.model)] == ModelRef(
            provider=fleet_default.provider,
            model=fleet_default.model,
            snapshot_pin=fleet_default.snapshot_pin,
        )


@pytest.mark.unit
def test_two_buy_vs_build_entries_are_catalog_only_not_fleet_defaults() -> None:
    """The Argo and in-house entries are pre-approved catalog members
    that no fleet agent declares as its compile-time default; they
    exist so an operator can point a RunDebriefer variant at either
    one for the 2-BM buy-vs-build debrief comparison."""
    fleet_identities = {
        (fleet_default.provider, fleet_default.model) for fleet_default in _FLEET_DEFAULTS
    }
    seeded_identities = {
        (entry.model_ref.provider, entry.model_ref.model) for entry in SEED_LANGUAGE_MODELS
    }
    extra_identities = seeded_identities - fleet_identities
    assert extra_identities == {
        (ARGO_PROVIDER_NAME, DEFAULT_RUN_DEBRIEF_MODEL.model),
        (_LOCAL_PROVIDER_NAME, "2bm-inhouse"),
    }


@pytest.mark.unit
def test_seed_pricing_figures_match_observability_pricing_table() -> None:
    """The seed copies PRICING numbers as literals; this pin catches a
    repricing that forgets the catalog side (or vice versa). Scoped to
    entries PRICING actually prices: the in-house entry is catalog-only
    by design and is checked separately below."""
    for entry in SEED_LANGUAGE_MODELS:
        key = (entry.model_ref.provider, entry.model_ref.model)
        if key not in PRICING:
            continue
        pricing = PRICING[key]
        assert entry.cost_basis == TokenPricing(
            input_per_mtok=pricing.input_per_mtok,
            output_per_mtok=pricing.output_per_mtok,
            cache_write_per_mtok=pricing.cache_write_per_mtok,
            cache_read_per_mtok=pricing.cache_read_per_mtok,
        )


@pytest.mark.unit
def test_overlay_built_from_seed_constants_equals_static_pricing_rows() -> None:
    """The day-1 no-behavior-change claim, pinned without a database:
    the mapping the pricing bridge would build from the seeded entries
    is exactly the static PRICING rows for those identities, so first
    boot's overlay install changes no metered figure. Scoped to
    entries PRICING actually prices, same carve-out as above."""
    overlay = {
        (entry.model_ref.provider, entry.model_ref.model): to_model_pricing(entry.cost_basis)
        for entry in SEED_LANGUAGE_MODELS
        if (entry.model_ref.provider, entry.model_ref.model) in PRICING
    }
    assert overlay == {key: PRICING[key] for key in overlay}


@pytest.mark.unit
def test_argo_entry_prices_and_serves_under_argo_not_anthropic() -> None:
    """The Argo entry must never be priced or served as `anthropic`:
    `ArgoLLM.chat` refuses a ModelRef priced any other way, because
    pricing resolves from `ModelRef.provider` while the route is
    chosen by config, and letting the two disagree would bill a
    facility-funded call at the deployment's own list rate."""
    argo_entries = [
        entry for entry in SEED_LANGUAGE_MODELS if entry.model_ref.provider == ARGO_PROVIDER_NAME
    ]
    assert len(argo_entries) == 1
    entry = argo_entries[0]
    assert entry.model_ref.model == DEFAULT_RUN_DEBRIEF_MODEL.model
    assert entry.model_ref.snapshot_pin is None
    assert entry.served_via == ServingRoute.ARGO
    assert entry.cost_basis == TokenPricing(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=2.00,
        cache_read_per_mtok=0.10,
    )
    assert entry.cost_basis == TokenPricing(
        input_per_mtok=PRICING[(ARGO_PROVIDER_NAME, entry.model_ref.model)].input_per_mtok,
        output_per_mtok=PRICING[(ARGO_PROVIDER_NAME, entry.model_ref.model)].output_per_mtok,
        cache_write_per_mtok=PRICING[
            (ARGO_PROVIDER_NAME, entry.model_ref.model)
        ].cache_write_per_mtok,
        cache_read_per_mtok=PRICING[
            (ARGO_PROVIDER_NAME, entry.model_ref.model)
        ].cache_read_per_mtok,
    )


@pytest.mark.unit
def test_in_house_entry_is_token_priced_and_has_no_static_pricing_row() -> None:
    """The in-house entry must carry a token price (a zero rate is
    legitimate for metered-free serving), never `GpuHourPricing`:
    `approve_language_model` refuses any entry priced per GPU-hour
    outright. It has no static PRICING row by design; its rate is
    catalog-only, set by the facility rather than mirrored from a
    vendor table."""
    local_entries = [
        entry for entry in SEED_LANGUAGE_MODELS if entry.model_ref.provider == _LOCAL_PROVIDER_NAME
    ]
    assert len(local_entries) == 1
    entry = local_entries[0]
    assert entry.served_via == ServingRoute.IN_HOUSE
    assert isinstance(entry.cost_basis, TokenPricing)
    assert entry.cost_basis == TokenPricing(
        input_per_mtok=0.0,
        output_per_mtok=0.0,
        cache_write_per_mtok=0.0,
        cache_read_per_mtok=0.0,
    )
    assert (entry.model_ref.provider, entry.model_ref.model) not in PRICING


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
        assert state.served_via == entry.served_via
        assert state.archivability == ArchivabilityTier.ALIAS


@pytest.mark.unit
async def test_seed_warns_and_preserves_stream_squatting_a_seed_id() -> None:
    """A stream that pre-exists at a deterministic seed id but was NOT
    written by the seed logs the stream_squatted WARNING (an operator
    must inspect it) and its events are never overwritten."""
    kernel = _kernel()
    entry = SEED_LANGUAGE_MODELS[0]
    language_model_id = language_model_seed_id(entry.model_ref.provider, entry.model_ref.model)
    squatter_event = LanguageModelDefined(
        language_model_id=language_model_id,
        name="Squatter Entry",
        provider=entry.model_ref.provider,
        model=entry.model_ref.model,
        snapshot_pin=None,
        served_via="Direct",
        endpoint_note=None,
        cost_basis=cost_basis_to_payload(
            TokenPricing(
                input_per_mtok=1.0,
                output_per_mtok=2.0,
                cache_write_per_mtok=1.5,
                cache_read_per_mtok=0.1,
            )
        ),
        data_tier="Internal",
        archivability="Alias",
        occurred_at=datetime(2026, 7, 11, 9, 0, 0, tzinfo=UTC),
    )
    await kernel.event_store.append(
        stream_type="LanguageModel",
        stream_id=language_model_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(squatter_event),
                payload=to_payload(squatter_event),
                occurred_at=squatter_event.occurred_at,
                event_id=UUID("01900000-0000-7000-8000-00000000f001"),
                command_name="DefineLanguageModel",
                correlation_id=UUID("01900000-0000-7000-8000-0000000000aa"),
                causation_id=None,
                principal_id=UUID("01900000-0000-7000-8000-000000000099"),
            )
        ],
    )

    with structlog.testing.capture_logs() as logs:
        await seed_language_models(kernel)

    squat_warnings = [log for log in logs if log["event"] == "language_model_seed.stream_squatted"]
    assert len(squat_warnings) == 1
    assert squat_warnings[0]["log_level"] == "warning"
    assert squat_warnings[0]["language_model_id"] == str(language_model_id)
    assert squat_warnings[0]["provider"] == entry.model_ref.provider
    assert squat_warnings[0]["model"] == entry.model_ref.model
    assert squat_warnings[0]["found_command_name"] == "DefineLanguageModel"

    events, version = await kernel.event_store.load("LanguageModel", language_model_id)
    assert version == 1
    assert [e.event_type for e in events] == ["LanguageModelDefined"]
    assert events[0].payload["name"] == "Squatter Entry"


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
