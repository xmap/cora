"""Unit tests for the Intent enum + PromotionReason VO.

Pin:
  - Intent enum values are exact strings (Trial / Production); StrEnum
    serializes naturally as those strings.
  - PromotionReason VO trims whitespace + validates length.
  - Open-enum stance: future values land additively without breaking
    DatasetRegistered events without the intent field.
"""

import pytest

from cora.data.aggregates.dataset import (
    DemotionReason,
    Intent,
    InvalidDemotionReasonError,
    InvalidPromotionReasonError,
    PromotionReason,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH

# ---------- Intent ----------


@pytest.mark.unit
def test_intent_values_match_locked_strings() -> None:
    """Pin the exact serialized strings — these are persisted in event
    payloads and breaking them is a payload-format change."""
    assert Intent.TRIAL.value == "Trial"
    assert Intent.PRODUCTION.value == "Production"
    assert Intent.RETRACTED.value == "Retracted"


@pytest.mark.unit
def test_intent_string_round_trip() -> None:
    """Intent("Trial") / ("Production") / ("Retracted") roundtrip cleanly
    via the StrEnum constructor — used by the evolver to rebuild from
    the raw string in the event payload."""
    assert Intent("Trial") is Intent.TRIAL
    assert Intent("Production") is Intent.PRODUCTION
    assert Intent("Retracted") is Intent.RETRACTED


@pytest.mark.unit
def test_intent_unknown_value_raises() -> None:
    """Unknown intent strings raise ValueError — protects against
    payload corruption / typos at fold time."""
    with pytest.raises(ValueError, match="Calibration"):
        Intent("Calibration")  # not a current value (open-enum future)


# ---------- PromotionReason ----------


@pytest.mark.unit
def test_promotion_reason_trims_whitespace() -> None:
    reason = PromotionReason("  passed peer review  ")
    assert reason.value == "passed peer review"


@pytest.mark.unit
def test_promotion_reason_accepts_max_length() -> None:
    at_max = "x" * REASON_MAX_LENGTH
    reason = PromotionReason(at_max)
    assert reason.value == at_max


@pytest.mark.unit
def test_promotion_reason_rejects_empty() -> None:
    with pytest.raises(InvalidPromotionReasonError):
        PromotionReason("")


@pytest.mark.unit
def test_promotion_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidPromotionReasonError):
        PromotionReason("   ")


@pytest.mark.unit
def test_promotion_reason_rejects_overlong() -> None:
    overlong = "x" * (REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidPromotionReasonError):
        PromotionReason(overlong)


@pytest.mark.unit
def test_promotion_reason_is_hashable_and_equatable() -> None:
    """Frozen dataclass: same trimmed value -> equal instances."""
    a = PromotionReason("passed review")
    b = PromotionReason("  passed review  ")  # trims to same
    assert a == b
    assert hash(a) == hash(b)


# ---------- DemotionReason (post-Q4 compensation primitive) ----------


@pytest.mark.unit
def test_demotion_reason_trims_whitespace() -> None:
    reason = DemotionReason("  calibration error  ")
    assert reason.value == "calibration error"


@pytest.mark.unit
def test_demotion_reason_accepts_max_length() -> None:
    at_max = "x" * REASON_MAX_LENGTH
    reason = DemotionReason(at_max)
    assert reason.value == at_max


@pytest.mark.unit
def test_demotion_reason_rejects_empty() -> None:
    with pytest.raises(InvalidDemotionReasonError):
        DemotionReason("")


@pytest.mark.unit
def test_demotion_reason_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidDemotionReasonError):
        DemotionReason("   ")


@pytest.mark.unit
def test_demotion_reason_rejects_overlong() -> None:
    overlong = "x" * (REASON_MAX_LENGTH + 1)
    with pytest.raises(InvalidDemotionReasonError):
        DemotionReason(overlong)


@pytest.mark.unit
def test_demotion_reason_is_hashable_and_equatable() -> None:
    """Frozen dataclass: same trimmed value -> equal instances."""
    a = DemotionReason("calibration error")
    b = DemotionReason("  calibration error  ")  # trims to same
    assert a == b
    assert hash(a) == hash(b)
