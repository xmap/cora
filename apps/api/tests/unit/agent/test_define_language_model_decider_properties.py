"""Property-based tests for `define_language_model.decide` (Agent BC).

Complements the example-based `test_define_language_model_decider.py`
with universal claims across generated inputs. The genesis decider is
pure

    (state, command, *, now, new_id) -> list[LanguageModelDefined]

Load-bearing properties:

  - Any non-None state always raises `LanguageModelAlreadyExistsError`
    carrying state.id (idempotency-as-error), regardless of command.
  - Any strictly negative token rate always raises
    `InvalidCostBasisError` (one poisoned rate would corrupt every
    projection the pricing bridge feeds).
  - On the happy path the single `LanguageModelDefined` carries the
    injected/passthrough fields, and the cost basis re-encodes to the
    canonical key set for any finite non-negative rates.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    InvalidCostBasisError,
    LanguageModel,
    LanguageModelAlreadyExistsError,
    LanguageModelDefined,
    LanguageModelName,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.define_language_model.command import DefineLanguageModel
from cora.agent.features.define_language_model.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_NAME = "Claude Sonnet 4.6"
_PROVIDER = "anthropic"
_MODEL = "claude-sonnet-4-6"
_TOKEN_COST = {
    "kind": "TokenPricing",
    "input_per_mtok": 3.0,
    "output_per_mtok": 15.0,
    "cache_write_per_mtok": 3.75,
    "cache_read_per_mtok": 0.3,
}

_rates = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_negative_rates = st.floats(min_value=-1e6, max_value=-1e-6, allow_nan=False, allow_infinity=False)


def _command(**overrides: object) -> DefineLanguageModel:
    base: dict[str, object] = {
        "name": _NAME,
        "provider": _PROVIDER,
        "model": _MODEL,
        "served_via": "Argo",
        "cost_basis": dict(_TOKEN_COST),
        "data_tier": "Internal",
        "archivability": "Alias",
    }
    base.update(overrides)
    return DefineLanguageModel(**base)  # type: ignore[arg-type]


def _state(*, language_model_id: UUID) -> LanguageModel:
    return LanguageModel(
        id=language_model_id,
        name=LanguageModelName(_NAME),
        model_ref=ModelRef(provider=_PROVIDER, model=_MODEL),
        served_via=ServingRoute.ARGO,
        cost_basis=TokenPricing(3.0, 15.0, 3.75, 0.3),
        data_tier=DataSensitivityTier.INTERNAL,
        archivability=ArchivabilityTier.ALIAS,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises LanguageModelAlreadyExistsError carrying state.id."""
    existing = _state(language_model_id=existing_id)
    with pytest.raises(LanguageModelAlreadyExistsError) as exc:
        decide(state=existing, command=_command(), now=now, new_id=new_id)
    assert exc.value.language_model_id == existing_id


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_empty_stream_emits_single_event_with_injected_fields(
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one LanguageModelDefined carrying the injected fields."""
    events = decide(state=None, command=_command(), now=now, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, LanguageModelDefined)
    assert event.language_model_id == new_id
    assert event.name == _NAME
    assert event.provider == _PROVIDER
    assert event.model == _MODEL
    assert event.served_via == "Argo"
    assert event.data_tier == "Internal"
    assert event.archivability == "Alias"
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    endpoint_note=printable_ascii_text(min_size=1, max_size=200),
    snapshot_pin=printable_ascii_text(min_size=1, max_size=100),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_threads_optional_fields_into_event(
    endpoint_note: str,
    snapshot_pin: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Optional command fields are threaded through onto the event."""
    events = decide(
        state=None,
        command=_command(endpoint_note=endpoint_note, snapshot_pin=snapshot_pin),
        now=now,
        new_id=new_id,
    )
    event = events[0]
    assert event.endpoint_note == endpoint_note
    assert event.snapshot_pin == snapshot_pin


@pytest.mark.unit
@given(
    input_rate=_rates,
    output_rate=_rates,
    cache_write_rate=_rates,
    cache_read_rate=_rates,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_token_pricing_reencodes_to_canonical_payload(
    input_rate: float,
    output_rate: float,
    cache_write_rate: float,
    cache_read_rate: float,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any finite non-negative rates survive decode + re-encode unchanged."""
    cost_basis: dict[str, Any] = {
        "kind": "TokenPricing",
        "input_per_mtok": input_rate,
        "output_per_mtok": output_rate,
        "cache_write_per_mtok": cache_write_rate,
        "cache_read_per_mtok": cache_read_rate,
    }
    events = decide(state=None, command=_command(cost_basis=cost_basis), now=now, new_id=new_id)
    assert events[0].cost_basis == cost_basis


@pytest.mark.unit
@given(
    bad_rate=_negative_rates,
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_negative_token_rate_always_raises_invalid_cost_basis(
    bad_rate: float,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any strictly negative rate raises InvalidCostBasisError."""
    cost_basis = dict(_TOKEN_COST)
    cost_basis["output_per_mtok"] = bad_rate
    with pytest.raises(InvalidCostBasisError):
        decide(state=None, command=_command(cost_basis=cost_basis), now=now, new_id=new_id)


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(endpoint_note="Argo prod gateway")
    first = decide(state=None, command=command, now=now, new_id=new_id)
    second = decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
