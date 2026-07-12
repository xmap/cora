"""Pure-decider tests for the `announce_language_model_retirement` slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.language_model import (
    ArchivabilityTier,
    DataSensitivityTier,
    InvalidLanguageModelReasonError,
    LanguageModel,
    LanguageModelCannotAnnounceRetirementError,
    LanguageModelName,
    LanguageModelNotFoundError,
    LanguageModelRetirementAnnounced,
    LanguageModelStatus,
    ServingRoute,
    TokenPricing,
)
from cora.agent.features.announce_language_model_retirement.command import (
    AnnounceLanguageModelRetirement,
)
from cora.agent.features.announce_language_model_retirement.decider import decide
from cora.shared.text_bounds import REASON_MAX_LENGTH

_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
_EFFECTIVE_AT = datetime(2026, 9, 30, 0, 0, 0, tzinfo=UTC)


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
def test_announces_retirement_for_an_approved_language_model() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    events = decide(
        state=entry,
        command=AnnounceLanguageModelRetirement(
            language_model_id=entry.id,
            reason="vendor sunset notice",
            effective_at=_EFFECTIVE_AT,
        ),
        now=_NOW,
    )
    assert events == [
        LanguageModelRetirementAnnounced(
            language_model_id=entry.id,
            reason="vendor sunset notice",
            effective_at=_EFFECTIVE_AT,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_announce_without_date_emits_none_effective_at() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    events = decide(
        state=entry,
        command=AnnounceLanguageModelRetirement(
            language_model_id=entry.id, reason="warning without a date"
        ),
        now=_NOW,
    )
    assert events[0].effective_at is None


@pytest.mark.unit
def test_not_found_when_state_is_none() -> None:
    with pytest.raises(LanguageModelNotFoundError):
        decide(
            state=None,
            command=AnnounceLanguageModelRetirement(language_model_id=uuid4(), reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        LanguageModelStatus.DEFINED,
        LanguageModelStatus.RETIREMENT_ANNOUNCED,
        LanguageModelStatus.RETIRED,
        LanguageModelStatus.DEPRECATED,
    ],
)
def test_cannot_announce_retirement_from_non_approved(status: LanguageModelStatus) -> None:
    entry = _language_model(status)
    with pytest.raises(LanguageModelCannotAnnounceRetirementError):
        decide(
            state=entry,
            command=AnnounceLanguageModelRetirement(language_model_id=entry.id, reason="x"),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_trims_via_value_object() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    events = decide(
        state=entry,
        command=AnnounceLanguageModelRetirement(
            language_model_id=entry.id, reason="  provider EOL notice  "
        ),
        now=_NOW,
    )
    assert events[0].reason == "provider EOL notice"


@pytest.mark.unit
def test_reason_empty_raises() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    with pytest.raises(InvalidLanguageModelReasonError):
        decide(
            state=entry,
            command=AnnounceLanguageModelRetirement(language_model_id=entry.id, reason="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_reason_over_cap_raises() -> None:
    entry = _language_model(LanguageModelStatus.APPROVED)
    with pytest.raises(InvalidLanguageModelReasonError):
        decide(
            state=entry,
            command=AnnounceLanguageModelRetirement(
                language_model_id=entry.id,
                reason="x" * (REASON_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )
