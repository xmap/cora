"""Pure-decider tests for the `deprecate_language_model` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    LanguageModel,
    LanguageModelCannotDeprecateError,
    LanguageModelDeprecated,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.deprecate_language_model.command import DeprecateLanguageModel
from cora.agent.features.deprecate_language_model.decider import decide
from cora.shared.deprecation import DeprecationReason

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
def test_deprecates_a_defined_language_model() -> None:
    entry = _language_model(LanguageModelStatus.DEFINED)
    events = decide(
        state=entry,
        command=DeprecateLanguageModel(
            language_model_id=entry.id, reason=DeprecationReason.SUPERSEDED
        ),
        now=_NOW,
    )
    assert events == [
        LanguageModelDeprecated(
            language_model_id=entry.id,
            reason="Superseded",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        LanguageModelStatus.APPROVED,
        LanguageModelStatus.RETIREMENT_ANNOUNCED,
    ],
)
def test_deprecates_from_every_later_pre_terminal_status(status: LanguageModelStatus) -> None:
    entry = _language_model(status)
    events = decide(
        state=entry,
        command=DeprecateLanguageModel(
            language_model_id=entry.id, reason=DeprecationReason.SUPERSEDED
        ),
        now=_NOW,
    )
    assert isinstance(events[0], LanguageModelDeprecated)
    assert events[0].reason == "Superseded"


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(LanguageModelNotFoundError):
        decide(
            state=None,
            command=DeprecateLanguageModel(
                language_model_id=uuid4(), reason=DeprecationReason.SUPERSEDED
            ),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [LanguageModelStatus.RETIRED, LanguageModelStatus.DEPRECATED],
)
def test_cannot_deprecate_a_terminal_language_model(status: LanguageModelStatus) -> None:
    entry = _language_model(status)
    with pytest.raises(LanguageModelCannotDeprecateError):
        decide(
            state=entry,
            command=DeprecateLanguageModel(
                language_model_id=entry.id, reason=DeprecationReason.SUPERSEDED
            ),
            now=_NOW,
        )
