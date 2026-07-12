"""Unit tests for the fleet-default LanguageModel catalog seed.

Pins the consistency contract: every model the shipped fleet declares
(RunDebriefer, CautionDrafter, and the ExperimentSteerer LLM-decide
default, whose identity the seed mirrors as literals across the tach
boundary) has a seeded catalog entry, born Approved, at a
deterministic id, with pricing figures matching the observability
PRICING table. Idempotency mirrors test_caution_drafter_seed.py.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
import structlog.testing

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    LanguageModelDefined,
    LanguageModelStatus,
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
    mirrors as literals across the tach boundary; the identity-set
    equality pins that no seed entry is orphaned either."""
    seeded_by_identity = {
        (entry.model_ref.provider, entry.model_ref.model): entry.model_ref
        for entry in SEED_LANGUAGE_MODELS
    }
    assert set(seeded_by_identity) == {
        (fleet_default.provider, fleet_default.model) for fleet_default in _FLEET_DEFAULTS
    }
    for fleet_default in _FLEET_DEFAULTS:
        assert seeded_by_identity[(fleet_default.provider, fleet_default.model)] == ModelRef(
            provider=fleet_default.provider,
            model=fleet_default.model,
            snapshot_pin=fleet_default.snapshot_pin,
        )


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
