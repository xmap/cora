"""Evolver tests for the LanguageModel aggregate."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.agent.aggregates.language_model.events import (
    LanguageModelApproved,
    LanguageModelDefined,
    LanguageModelDeprecated,
    LanguageModelRetired,
    LanguageModelRetirementAnnounced,
    cost_basis_to_payload,
)
from cora.agent.aggregates.language_model.evolver import fold
from cora.agent.aggregates.language_model.state import (
    ArchivabilityTier,
    DataSensitivityTier,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)

_T0 = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(minutes=10)
_T2 = _T0 + timedelta(minutes=20)
_T3 = _T0 + timedelta(minutes=30)

_EFFECTIVE_AT = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)

_PRICING = TokenPricing(
    input_per_mtok=3.0,
    output_per_mtok=15.0,
    cache_write_per_mtok=6.0,
    cache_read_per_mtok=0.3,
)


def _genesis(*, language_model_id: object | None = None) -> LanguageModelDefined:
    return LanguageModelDefined(
        language_model_id=language_model_id or uuid4(),  # type: ignore[arg-type]
        name="Claude Sonnet 4.5",
        provider="anthropic",
        model="claude-sonnet-4-5",
        snapshot_pin=None,
        served_via="Direct",
        endpoint_note=None,
        cost_basis=cost_basis_to_payload(_PRICING),
        data_tier="Internal",
        archivability="Alias",
        occurred_at=_T0,
    )


@pytest.mark.unit
def test_empty_stream_folds_to_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_genesis_folds_to_defined_state() -> None:
    e = _genesis()
    state = fold([e])
    assert state is not None
    assert state.id == e.language_model_id
    assert state.status is LanguageModelStatus.DEFINED
    assert state.name.value == "Claude Sonnet 4.5"
    assert state.model_ref.provider == "anthropic"
    assert state.model_ref.model == "claude-sonnet-4-5"
    assert state.served_via is ServingRoute.DIRECT
    assert state.cost_basis == _PRICING
    assert state.data_tier is DataSensitivityTier.INTERNAL
    assert state.archivability is ArchivabilityTier.ALIAS
    assert state.retirement_effective_at is None
    assert state.end_reason is None


@pytest.mark.unit
def test_announced_then_reasonless_retirement_keeps_announcement_context() -> None:
    """Defined -> Approved -> RetirementAnnounced -> Retired(reason=None)
    folds to RETIRED while KEEPING the announcement's reason and
    effective_at: the folded state never loses end-of-life context on
    the way to terminal."""
    language_model_id = uuid4()
    e1 = _genesis(language_model_id=language_model_id)
    e2 = LanguageModelApproved(language_model_id=language_model_id, occurred_at=_T1)
    e3 = LanguageModelRetirementAnnounced(
        language_model_id=language_model_id,
        reason="Vendor sunsets the alias",
        effective_at=_EFFECTIVE_AT,
        occurred_at=_T2,
    )
    e4 = LanguageModelRetired(language_model_id=language_model_id, reason=None, occurred_at=_T3)
    state = fold([e1, e2, e3, e4])
    assert state is not None
    assert state.status is LanguageModelStatus.RETIRED
    assert state.end_reason is not None
    assert state.end_reason.value == "Vendor sunsets the alias"
    assert state.retirement_effective_at == _EFFECTIVE_AT


@pytest.mark.unit
def test_retirement_with_own_reason_replaces_the_announcement_reason() -> None:
    language_model_id = uuid4()
    e1 = _genesis(language_model_id=language_model_id)
    e2 = LanguageModelApproved(language_model_id=language_model_id, occurred_at=_T1)
    e3 = LanguageModelRetirementAnnounced(
        language_model_id=language_model_id,
        reason="Vendor sunsets the alias",
        effective_at=_EFFECTIVE_AT,
        occurred_at=_T2,
    )
    e4 = LanguageModelRetired(
        language_model_id=language_model_id,
        reason="Endpoint returned 404 ahead of schedule",
        occurred_at=_T3,
    )
    state = fold([e1, e2, e3, e4])
    assert state is not None
    assert state.status is LanguageModelStatus.RETIRED
    assert state.end_reason is not None
    assert state.end_reason.value == "Endpoint returned 404 ahead of schedule"


@pytest.mark.unit
def test_announcement_without_effective_date_folds_with_none_cutoff() -> None:
    """A vendor warning with no date is a real announcement: status
    flips and the reason lands while retirement_effective_at stays
    None."""
    language_model_id = uuid4()
    e1 = _genesis(language_model_id=language_model_id)
    e2 = LanguageModelApproved(language_model_id=language_model_id, occurred_at=_T1)
    e3 = LanguageModelRetirementAnnounced(
        language_model_id=language_model_id,
        reason="Deprecation notice without a cutoff",
        effective_at=None,
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is LanguageModelStatus.RETIREMENT_ANNOUNCED
    assert state.retirement_effective_at is None
    assert state.end_reason is not None
    assert state.end_reason.value == "Deprecation notice without a cutoff"


@pytest.mark.unit
def test_deprecated_folds_to_deprecated_with_end_reason() -> None:
    language_model_id = uuid4()
    e1 = _genesis(language_model_id=language_model_id)
    e2 = LanguageModelApproved(language_model_id=language_model_id, occurred_at=_T1)
    e3 = LanguageModelDeprecated(
        language_model_id=language_model_id,
        reason="Superseded",
        occurred_at=_T2,
    )
    state = fold([e1, e2, e3])
    assert state is not None
    assert state.status is LanguageModelStatus.DEPRECATED
    assert state.end_reason is not None
    assert state.end_reason.value == "Superseded"


@pytest.mark.unit
def test_approved_applied_to_empty_state_raises() -> None:
    """The shared `require_state` helper raises on transition-before-genesis."""
    e = LanguageModelApproved(language_model_id=uuid4(), occurred_at=_T0)
    with pytest.raises(ValueError, match="LanguageModelApproved"):
        fold([e])
