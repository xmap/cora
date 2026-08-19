"""Pure-decider tests for the `approve_language_model` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    GpuHourPricing,
    LanguageModel,
    LanguageModelApproved,
    LanguageModelCannotApproveError,
    LanguageModelCannotApproveGpuHourBasisError,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.approve_language_model.command import ApproveLanguageModel
from cora.agent.features.approve_language_model.decider import decide

_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _language_model(
    status: LanguageModelStatus,
    *,
    language_model_id: UUID | None = None,
    served_via: ServingRoute = ServingRoute.ARGO,
    cost_basis: TokenPricing | GpuHourPricing | None = None,
) -> LanguageModel:
    return LanguageModel(
        id=language_model_id or uuid4(),
        name=LanguageModelName("Claude Sonnet 4.6"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        served_via=served_via,
        cost_basis=cost_basis
        if cost_basis is not None
        else TokenPricing(
            input_per_mtok=3.0,
            output_per_mtok=15.0,
            cache_write_per_mtok=3.75,
            cache_read_per_mtok=0.3,
        ),
        data_tier=DataSensitivityTier.INTERNAL,
        archivability=ArchivabilityTier.ALIAS,
        status=status,
    )


@pytest.mark.unit
def test_approves_a_defined_language_model() -> None:
    entry = _language_model(LanguageModelStatus.DEFINED)
    events = decide(state=entry, command=ApproveLanguageModel(language_model_id=entry.id), now=_NOW)
    assert events == [LanguageModelApproved(language_model_id=entry.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(LanguageModelNotFoundError):
        decide(state=None, command=ApproveLanguageModel(language_model_id=uuid4()), now=_NOW)


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        LanguageModelStatus.APPROVED,
        LanguageModelStatus.RETIREMENT_ANNOUNCED,
        LanguageModelStatus.RETIRED,
        LanguageModelStatus.DEPRECATED,
    ],
)
def test_cannot_approve_from_non_defined(status: LanguageModelStatus) -> None:
    entry = _language_model(status)
    with pytest.raises(LanguageModelCannotApproveError):
        decide(state=entry, command=ApproveLanguageModel(language_model_id=entry.id), now=_NOW)


@pytest.mark.unit
@pytest.mark.parametrize(
    "served_via",
    [ServingRoute.IN_HOUSE, ServingRoute.DIRECT, ServingRoute.ARGO],
)
def test_gpu_hour_basis_cannot_be_approved_on_any_route(served_via: ServingRoute) -> None:
    """A GPU-hour basis is bridge-skipped on every route, so it can never go live."""
    entry = _language_model(
        LanguageModelStatus.DEFINED,
        served_via=served_via,
        cost_basis=GpuHourPricing(usd_per_gpu_hour=12.5),
    )
    with pytest.raises(LanguageModelCannotApproveGpuHourBasisError) as exc:
        decide(state=entry, command=ApproveLanguageModel(language_model_id=entry.id), now=_NOW)
    assert exc.value.language_model_id == entry.id


@pytest.mark.unit
def test_in_house_metered_free_zero_token_pricing_approves() -> None:
    """Metered-free is a DECLARED zero token price, not an absent one, so it approves."""
    entry = _language_model(
        LanguageModelStatus.DEFINED,
        served_via=ServingRoute.IN_HOUSE,
        cost_basis=TokenPricing(
            input_per_mtok=0.0,
            output_per_mtok=0.0,
            cache_write_per_mtok=0.0,
            cache_read_per_mtok=0.0,
        ),
    )
    events = decide(state=entry, command=ApproveLanguageModel(language_model_id=entry.id), now=_NOW)
    assert events == [LanguageModelApproved(language_model_id=entry.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_in_house_token_pricing_approves() -> None:
    entry = _language_model(
        LanguageModelStatus.DEFINED,
        served_via=ServingRoute.IN_HOUSE,
        cost_basis=TokenPricing(
            input_per_mtok=0.4,
            output_per_mtok=0.8,
            cache_write_per_mtok=0.4,
            cache_read_per_mtok=0.04,
        ),
    )
    events = decide(state=entry, command=ApproveLanguageModel(language_model_id=entry.id), now=_NOW)
    assert events == [LanguageModelApproved(language_model_id=entry.id, occurred_at=_NOW)]
