"""Pure-decider tests for the `retire_language_model` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    InvalidLanguageModelReasonError,
    LanguageModel,
    LanguageModelCannotRetireError,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelRetired,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.retire_language_model.command import RetireLanguageModel
from cora.agent.features.retire_language_model.decider import decide
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _language_model(
    status: LanguageModelStatus, *, language_model_id: UUID | None = None
) -> LanguageModel:
    return LanguageModel(
        id=language_model_id or uuid4(),
        name=LanguageModelName("Claude Sonnet 4.6"),
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        served_via=ServingRoute.ARGO,
        cost_basis=TokenPricing(
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
def test_retires_an_approved_language_model_with_reason() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    events = decide(
        state=entry,
        command=RetireLanguageModel(language_model_id=entry.id, reason="provider removed it"),
        now=_NOW,
    )
    assert events == [
        LanguageModelRetired(
            language_model_id=entry.id,
            reason="provider removed it",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_retires_an_announced_language_model_with_no_reason() -> None:
    entry = _language_model(LanguageModelStatus.RETIREMENT_ANNOUNCED)
    events = decide(
        state=entry,
        command=RetireLanguageModel(language_model_id=entry.id, reason=None),
        now=_NOW,
    )
    assert events[0].reason is None


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(LanguageModelNotFoundError):
        decide(state=None, command=RetireLanguageModel(language_model_id=uuid4()), now=_NOW)


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        LanguageModelStatus.DEFINED,
        LanguageModelStatus.RETIRED,
        LanguageModelStatus.DEPRECATED,
    ],
)
def test_cannot_retire_from_disallowed_status(status: LanguageModelStatus) -> None:
    entry = _language_model(status)
    with pytest.raises(LanguageModelCannotRetireError):
        decide(state=entry, command=RetireLanguageModel(language_model_id=entry.id), now=_NOW)


@pytest.mark.unit
def test_invalid_reason_raises() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    with pytest.raises(InvalidLanguageModelReasonError):
        decide(
            state=entry,
            command=RetireLanguageModel(
                language_model_id=entry.id,
                reason="x" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_trims_via_value_object() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    events = decide(
        state=entry,
        command=RetireLanguageModel(language_model_id=entry.id, reason="  model gone  "),
        now=_NOW,
    )
    assert events[0].reason == "model gone"
