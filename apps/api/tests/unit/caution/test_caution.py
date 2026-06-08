"""CautionText / CautionWorkaround / CautionTag VOs + enums + targets + aggregate.

`CautionAlreadyExistsError` / `CautionNotFoundError` / `CautionCannotSupersedeError`
/ `CautionCannotRetireError` are exercised at the decider / handler layer.
"""

from uuid import uuid4

import pytest

from cora.caution.aggregates.caution import (
    CAUTION_TAG_MAX_LENGTH,
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    AssetTarget,
    Caution,
    CautionCategory,
    CautionRetireReason,
    CautionSeverity,
    CautionStatus,
    CautionTag,
    CautionText,
    CautionWorkaround,
    InvalidCautionTagError,
    InvalidCautionTextError,
    InvalidCautionWorkaroundError,
    ProcedureTarget,
)
from cora.shared.identity import ActorId

# ---------- CautionText VO ----------


@pytest.mark.unit
def test_caution_text_accepts_normal_string() -> None:
    text = CautionText("hexapod stalls below 0.5 mm/s")
    assert text.value == "hexapod stalls below 0.5 mm/s"


@pytest.mark.unit
def test_caution_text_trims_whitespace() -> None:
    text = CautionText("  encoder reverses near home  ")
    assert text.value == "encoder reverses near home"


@pytest.mark.unit
def test_caution_text_rejects_empty_string() -> None:
    with pytest.raises(InvalidCautionTextError):
        CautionText("")


@pytest.mark.unit
def test_caution_text_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCautionTextError):
        CautionText("   \t\n   ")


@pytest.mark.unit
def test_caution_text_rejects_too_long() -> None:
    with pytest.raises(InvalidCautionTextError):
        CautionText("a" * (CAUTION_TEXT_MAX_LENGTH + 1))


@pytest.mark.unit
def test_caution_text_accepts_max_length() -> None:
    text = CautionText("a" * CAUTION_TEXT_MAX_LENGTH)
    assert len(text.value) == CAUTION_TEXT_MAX_LENGTH


@pytest.mark.unit
def test_caution_text_is_frozen() -> None:
    text = CautionText("body")
    with pytest.raises(AttributeError):
        text.value = "other"  # type: ignore[misc]


# ---------- CautionWorkaround VO ----------


@pytest.mark.unit
def test_caution_workaround_accepts_normal_string() -> None:
    workaround = CautionWorkaround("run at 0.6 mm/s minimum")
    assert workaround.value == "run at 0.6 mm/s minimum"


@pytest.mark.unit
def test_caution_workaround_trims_whitespace() -> None:
    workaround = CautionWorkaround("  use macro X instead  ")
    assert workaround.value == "use macro X instead"


@pytest.mark.unit
def test_caution_workaround_rejects_empty_string() -> None:
    with pytest.raises(InvalidCautionWorkaroundError):
        CautionWorkaround("")


@pytest.mark.unit
def test_caution_workaround_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCautionWorkaroundError):
        CautionWorkaround("   ")


@pytest.mark.unit
def test_caution_workaround_rejects_too_long() -> None:
    with pytest.raises(InvalidCautionWorkaroundError):
        CautionWorkaround("a" * (CAUTION_WORKAROUND_MAX_LENGTH + 1))


@pytest.mark.unit
def test_caution_workaround_accepts_max_length() -> None:
    workaround = CautionWorkaround("a" * CAUTION_WORKAROUND_MAX_LENGTH)
    assert len(workaround.value) == CAUTION_WORKAROUND_MAX_LENGTH


# ---------- CautionTag VO ----------


@pytest.mark.unit
def test_caution_tag_accepts_normal_string() -> None:
    tag = CautionTag("low-speed-stall")
    assert tag.value == "low-speed-stall"


@pytest.mark.unit
def test_caution_tag_trims_whitespace() -> None:
    tag = CautionTag("  beam-stability  ")
    assert tag.value == "beam-stability"


@pytest.mark.unit
def test_caution_tag_rejects_empty_string() -> None:
    with pytest.raises(InvalidCautionTagError):
        CautionTag("")


@pytest.mark.unit
def test_caution_tag_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCautionTagError):
        CautionTag("   ")


@pytest.mark.unit
def test_caution_tag_rejects_too_long() -> None:
    with pytest.raises(InvalidCautionTagError):
        CautionTag("a" * (CAUTION_TAG_MAX_LENGTH + 1))


@pytest.mark.unit
def test_caution_tag_accepts_max_length() -> None:
    tag = CautionTag("a" * CAUTION_TAG_MAX_LENGTH)
    assert len(tag.value) == CAUTION_TAG_MAX_LENGTH


# ---------- CautionStatus enum (3 values, locked) ----------


@pytest.mark.unit
def test_caution_status_has_three_locked_values() -> None:
    assert {s.value for s in CautionStatus} == {"Active", "Superseded", "Retired"}


@pytest.mark.unit
def test_caution_status_active_is_initial() -> None:
    assert CautionStatus.ACTIVE.value == "Active"


# ---------- CautionSeverity enum (3 values, ANSI Z535 downshifted) ----------


@pytest.mark.unit
def test_caution_severity_has_three_locked_values() -> None:
    assert {s.value for s in CautionSeverity} == {"Notice", "Caution", "Warning"}


@pytest.mark.unit
def test_caution_severity_has_no_danger_tier() -> None:
    """No Danger tier — formal lockout belongs to Safety BC Clearance."""
    assert "Danger" not in {s.value for s in CautionSeverity}


# ---------- CautionCategory enum (6 values, closed day-one) ----------


@pytest.mark.unit
def test_caution_category_has_six_locked_values() -> None:
    assert {c.value for c in CautionCategory} == {
        "Wear",
        "Calibration",
        "Wiring",
        "OperationalWindow",
        "InterlockQuirk",
        "ProcedureGotcha",
    }


# ---------- CautionRetireReason enum (3 values, closed) ----------


@pytest.mark.unit
def test_caution_retire_reason_has_three_locked_values() -> None:
    assert {r.value for r in CautionRetireReason} == {
        "Resolved",
        "NoLongerApplies",
        "WrongTarget",
    }


# ---------- Target discriminated union ----------


@pytest.mark.unit
def test_asset_target_carries_asset_id() -> None:
    aid = uuid4()
    target = AssetTarget(asset_id=aid)
    assert target.asset_id == aid


@pytest.mark.unit
def test_procedure_target_carries_procedure_id() -> None:
    pid = uuid4()
    target = ProcedureTarget(procedure_id=pid)
    assert target.procedure_id == pid


@pytest.mark.unit
def test_asset_and_procedure_targets_are_not_equal_with_same_uuid() -> None:
    """The discriminator survives equality even with overlapping UUID."""
    shared = uuid4()
    a = AssetTarget(asset_id=shared)
    p = ProcedureTarget(procedure_id=shared)
    assert a != p


# ---------- Caution aggregate dataclass ----------


def _minimal_caution() -> Caution:
    return Caution(
        id=uuid4(),
        target=AssetTarget(asset_id=uuid4()),
        category=CautionCategory.WEAR,
        severity=CautionSeverity.CAUTION,
        text=CautionText("hexapod stalls below 0.5 mm/s"),
        workaround=CautionWorkaround("run at 0.6 mm/s"),
        authored_by=ActorId(uuid4()),
    )


@pytest.mark.unit
def test_caution_aggregate_is_frozen() -> None:
    caution = _minimal_caution()
    with pytest.raises(AttributeError):
        caution.status = CautionStatus.RETIRED  # type: ignore[misc]


@pytest.mark.unit
def test_caution_status_defaults_to_active_at_construction() -> None:
    """The dataclass default mirrors the genesis-evolver-sets-Active convention."""
    caution = _minimal_caution()
    assert caution.status == CautionStatus.ACTIVE


@pytest.mark.unit
def test_caution_tags_default_to_empty_set() -> None:
    caution = _minimal_caution()
    assert caution.tags == frozenset()


@pytest.mark.unit
def test_caution_expires_at_defaults_to_none() -> None:
    caution = _minimal_caution()
    assert caution.expires_at is None


@pytest.mark.unit
def test_caution_propagate_to_children_defaults_to_false() -> None:
    """Anti-hook #8: explicit-opt-in only (AVEVA AF template-inheritance guard)."""
    caution = _minimal_caution()
    assert caution.propagate_to_children is False


@pytest.mark.unit
def test_caution_parent_id_defaults_to_none() -> None:
    caution = _minimal_caution()
    assert caution.parent_id is None


@pytest.mark.unit
def test_caution_superseded_by_caution_id_defaults_to_none() -> None:
    caution = _minimal_caution()
    assert caution.superseded_by_caution_id is None


@pytest.mark.unit
def test_caution_retired_reason_defaults_to_none() -> None:
    caution = _minimal_caution()
    assert caution.retired_reason is None


# ---------- Length-constant locks ----------


@pytest.mark.unit
def test_max_length_constants_are_pinned() -> None:
    assert CAUTION_TEXT_MAX_LENGTH == 2000
    assert CAUTION_WORKAROUND_MAX_LENGTH == 2000
    assert CAUTION_TAG_MAX_LENGTH == 50
