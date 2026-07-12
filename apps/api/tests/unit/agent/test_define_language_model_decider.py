"""Pure-decider tests for the `define_language_model` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import InvalidModelRefError, ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    InvalidCostBasisError,
    InvalidEndpointNoteError,
    InvalidLanguageModelNameError,
    LanguageModel,
    LanguageModelAlreadyExistsError,
    LanguageModelDefined,
    LanguageModelName,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.define_language_model.command import DefineLanguageModel
from cora.agent.features.define_language_model.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = uuid4()
_TOKEN_COST = {
    "kind": "TokenPricing",
    "input_per_mtok": 3.0,
    "output_per_mtok": 15.0,
    "cache_write_per_mtok": 3.75,
    "cache_read_per_mtok": 0.3,
}
_GPU_COST = {"kind": "GpuHourPricing", "usd_per_gpu_hour": 12.5}


def _command(**overrides: object) -> DefineLanguageModel:
    base: dict[str, object] = {
        "name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "served_via": "Argo",
        "cost_basis": dict(_TOKEN_COST),
        "data_tier": "Internal",
        "archivability": "Alias",
    }
    base.update(overrides)
    return DefineLanguageModel(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_minimal_command_emits_single_language_model_defined() -> None:
    events = decide(state=None, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert len(events) == 1
    assert isinstance(events[0], LanguageModelDefined)
    e = events[0]
    assert e.language_model_id == _NEW_ID
    assert e.name == "Claude Sonnet 4.6"
    assert e.provider == "anthropic"
    assert e.model == "claude-sonnet-4-6"
    assert e.snapshot_pin is None
    assert e.served_via == "Argo"
    assert e.endpoint_note is None
    assert e.cost_basis == _TOKEN_COST
    assert e.data_tier == "Internal"
    assert e.archivability == "Alias"
    assert e.occurred_at == _NOW


@pytest.mark.unit
def test_full_command_carries_all_optional_fields() -> None:
    events = decide(
        state=None,
        command=_command(
            snapshot_pin="claude-sonnet-4-6-20261101",
            endpoint_note="Argo prod gateway, imaging tenancy",
        ),
        now=_NOW,
        new_id=_NEW_ID,
    )
    e = events[0]
    assert e.snapshot_pin == "claude-sonnet-4-6-20261101"
    assert e.endpoint_note == "Argo prod gateway, imaging tenancy"


@pytest.mark.unit
def test_gpu_hour_cost_basis_carries_through() -> None:
    events = decide(
        state=None,
        command=_command(served_via="InHouse", cost_basis=dict(_GPU_COST)),
        now=_NOW,
        new_id=_NEW_ID,
    )
    e = events[0]
    assert e.served_via == "InHouse"
    assert e.cost_basis == _GPU_COST


@pytest.mark.unit
def test_genesis_collision_raises_already_exists() -> None:
    existing = LanguageModel(
        id=_NEW_ID,
        name=LanguageModelName("Claude Sonnet 4.6"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        served_via=ServingRoute.ARGO,
        cost_basis=TokenPricing(3.0, 15.0, 3.75, 0.3),
        data_tier=DataSensitivityTier.INTERNAL,
        archivability=ArchivabilityTier.ALIAS,
    )
    assert existing.status is LanguageModelStatus.DEFINED
    with pytest.raises(LanguageModelAlreadyExistsError):
        decide(state=existing, command=_command(), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_name_raises() -> None:
    with pytest.raises(InvalidLanguageModelNameError):
        decide(state=None, command=_command(name=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_provider_raises() -> None:
    with pytest.raises(InvalidModelRefError):
        decide(state=None, command=_command(provider=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_model_raises() -> None:
    with pytest.raises(InvalidModelRefError):
        decide(state=None, command=_command(model=" "), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_whitespace_only_snapshot_pin_raises() -> None:
    with pytest.raises(InvalidModelRefError):
        decide(state=None, command=_command(snapshot_pin="  "), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_unknown_served_via_raises() -> None:
    with pytest.raises(ValueError, match="ServingRoute"):
        decide(state=None, command=_command(served_via="Carrier"), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_unknown_data_tier_raises() -> None:
    with pytest.raises(ValueError, match="DataSensitivityTier"):
        decide(state=None, command=_command(data_tier="TopSecret"), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_unknown_archivability_raises() -> None:
    with pytest.raises(ValueError, match="ArchivabilityTier"):
        decide(state=None, command=_command(archivability="Frozen"), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_endpoint_note_raises() -> None:
    with pytest.raises(InvalidEndpointNoteError):
        decide(state=None, command=_command(endpoint_note=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_unknown_cost_basis_kind_raises_invalid_cost_basis() -> None:
    with pytest.raises(InvalidCostBasisError):
        decide(
            state=None,
            command=_command(cost_basis={"kind": "FlatFee", "usd": 1.0}),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_missing_cost_basis_kind_raises_invalid_cost_basis() -> None:
    with pytest.raises(InvalidCostBasisError):
        decide(
            state=None,
            command=_command(cost_basis={"usd_per_gpu_hour": 12.5}),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_negative_token_rate_raises_invalid_cost_basis() -> None:
    bad = dict(_TOKEN_COST)
    bad["input_per_mtok"] = -3.0
    with pytest.raises(InvalidCostBasisError):
        decide(state=None, command=_command(cost_basis=bad), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_negative_gpu_hour_rate_raises_invalid_cost_basis() -> None:
    with pytest.raises(InvalidCostBasisError):
        decide(
            state=None,
            command=_command(cost_basis={"kind": "GpuHourPricing", "usd_per_gpu_hour": -1.0}),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_extraneous_cost_basis_keys_dropped_from_event() -> None:
    """The decider re-encodes the decoded CostBasis, so the stored
    payload carries exactly the canonical key set per kind."""
    padded = dict(_TOKEN_COST)
    padded["contract_number"] = "ANL-2026-042"
    events = decide(state=None, command=_command(cost_basis=padded), now=_NOW, new_id=_NEW_ID)
    assert events[0].cost_basis == _TOKEN_COST


@pytest.mark.unit
def test_event_uses_handler_supplied_now_and_new_id() -> None:
    """Non-determinism principle: decider takes now + new_id as inputs."""
    custom_now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    custom_id = uuid4()
    events = decide(state=None, command=_command(), now=custom_now, new_id=custom_id)
    assert events[0].occurred_at == custom_now
    assert events[0].language_model_id == custom_id


@pytest.mark.unit
def test_value_object_trim_propagates() -> None:
    """Name + ModelRef VOs trim; the decider passes the trimmed values."""
    events = decide(
        state=None,
        command=_command(name="  Claude Sonnet 4.6  ", provider="  anthropic  "),
        now=_NOW,
        new_id=_NEW_ID,
    )
    e = events[0]
    assert e.name == "Claude Sonnet 4.6"
    assert e.provider == "anthropic"
