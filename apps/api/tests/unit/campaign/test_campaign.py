"""CampaignName / CampaignDescription / CampaignTag VOs + enums + aggregate defaults.

`CampaignAlreadyExistsError` / `CampaignNotFoundError` / the five
`CampaignCannot<Verb>Error` classes are exercised at the decider /
handler layer.
"""

from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    CAMPAIGN_DESCRIPTION_MAX_LENGTH,
    CAMPAIGN_EXTERNAL_ID_MAX_LENGTH,
    CAMPAIGN_NAME_MAX_LENGTH,
    CAMPAIGN_TAG_MAX_LENGTH,
    Campaign,
    CampaignDescription,
    CampaignIntent,
    CampaignName,
    CampaignStatus,
    CampaignTag,
    InvalidCampaignDescriptionError,
    InvalidCampaignNameError,
    InvalidCampaignTagError,
)
from cora.shared.text_bounds import REASON_MAX_LENGTH

_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-00000000c001")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000c099")


# ---------- length constants ----------


@pytest.mark.unit
def test_length_constants_match_design_memo() -> None:
    """6i-a lock per project_campaign_design.md."""
    assert CAMPAIGN_NAME_MAX_LENGTH == 200
    assert CAMPAIGN_DESCRIPTION_MAX_LENGTH == 2000
    assert CAMPAIGN_TAG_MAX_LENGTH == 50
    assert REASON_MAX_LENGTH == 500
    assert CAMPAIGN_EXTERNAL_ID_MAX_LENGTH == 100


# ---------- CampaignStatus enum ----------


@pytest.mark.unit
def test_campaign_status_values_locked() -> None:
    """5-state lock per BC-map line 94 + design memo."""
    assert CampaignStatus.PLANNED.value == "Planned"
    assert CampaignStatus.ACTIVE.value == "Active"
    assert CampaignStatus.HELD.value == "Held"
    assert CampaignStatus.CLOSED.value == "Closed"
    assert CampaignStatus.ABANDONED.value == "Abandoned"


@pytest.mark.unit
def test_campaign_status_has_exactly_five_members() -> None:
    """PackML's 17-state cascade is the anti-pattern; lock at 5."""
    assert len(list(CampaignStatus)) == 5


# ---------- CampaignIntent enum ----------


@pytest.mark.unit
def test_campaign_intent_values_locked() -> None:
    """4 closed intent-shape values day-1; technique-tagging lives on tags."""
    assert CampaignIntent.SERIES.value == "Series"
    assert CampaignIntent.SWEEP.value == "Sweep"
    assert CampaignIntent.COORDINATION.value == "Coordination"
    assert CampaignIntent.BLOCK.value == "Block"


@pytest.mark.unit
def test_campaign_intent_has_exactly_four_members() -> None:
    """Shape (Series/Sweep/Coordination/Block) vs purpose-tag separation."""
    assert len(list(CampaignIntent)) == 4


# ---------- CampaignName VO ----------


@pytest.mark.unit
def test_campaign_name_accepts_normal_string() -> None:
    name = CampaignName("In-situ heating series #42")
    assert name.value == "In-situ heating series #42"


@pytest.mark.unit
def test_campaign_name_trims_whitespace() -> None:
    name = CampaignName("  beam-time block May 16  ")
    assert name.value == "beam-time block May 16"


@pytest.mark.unit
def test_campaign_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidCampaignNameError):
        CampaignName("")


@pytest.mark.unit
def test_campaign_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCampaignNameError):
        CampaignName("   \t\n   ")


@pytest.mark.unit
def test_campaign_name_rejects_too_long() -> None:
    with pytest.raises(InvalidCampaignNameError):
        CampaignName("a" * (CAMPAIGN_NAME_MAX_LENGTH + 1))


@pytest.mark.unit
def test_campaign_name_accepts_max_length() -> None:
    name = CampaignName("a" * CAMPAIGN_NAME_MAX_LENGTH)
    assert len(name.value) == CAMPAIGN_NAME_MAX_LENGTH


@pytest.mark.unit
def test_campaign_name_is_frozen() -> None:
    name = CampaignName("body")
    with pytest.raises(AttributeError):
        name.value = "other"  # type: ignore[misc]


# ---------- CampaignDescription VO ----------


@pytest.mark.unit
def test_campaign_description_accepts_normal_string() -> None:
    desc = CampaignDescription("Sweep over LiCoO2 cells; 30C charge to 80%.")
    assert desc.value == "Sweep over LiCoO2 cells; 30C charge to 80%."


@pytest.mark.unit
def test_campaign_description_trims_whitespace() -> None:
    desc = CampaignDescription("  multimodal EDD + tomo block  ")
    assert desc.value == "multimodal EDD + tomo block"


@pytest.mark.unit
def test_campaign_description_rejects_empty_string() -> None:
    with pytest.raises(InvalidCampaignDescriptionError):
        CampaignDescription("")


@pytest.mark.unit
def test_campaign_description_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCampaignDescriptionError):
        CampaignDescription("   ")


@pytest.mark.unit
def test_campaign_description_rejects_too_long() -> None:
    with pytest.raises(InvalidCampaignDescriptionError):
        CampaignDescription("a" * (CAMPAIGN_DESCRIPTION_MAX_LENGTH + 1))


@pytest.mark.unit
def test_campaign_description_accepts_max_length() -> None:
    desc = CampaignDescription("a" * CAMPAIGN_DESCRIPTION_MAX_LENGTH)
    assert len(desc.value) == CAMPAIGN_DESCRIPTION_MAX_LENGTH


# ---------- CampaignTag VO ----------


@pytest.mark.unit
def test_campaign_tag_accepts_normal_string() -> None:
    tag = CampaignTag("battery")
    assert tag.value == "battery"


@pytest.mark.unit
def test_campaign_tag_trims_whitespace() -> None:
    tag = CampaignTag("  operando  ")
    assert tag.value == "operando"


@pytest.mark.unit
def test_campaign_tag_rejects_empty_string() -> None:
    with pytest.raises(InvalidCampaignTagError):
        CampaignTag("")


@pytest.mark.unit
def test_campaign_tag_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidCampaignTagError):
        CampaignTag("   ")


@pytest.mark.unit
def test_campaign_tag_rejects_too_long() -> None:
    with pytest.raises(InvalidCampaignTagError):
        CampaignTag("a" * (CAMPAIGN_TAG_MAX_LENGTH + 1))


@pytest.mark.unit
def test_campaign_tag_accepts_max_length() -> None:
    tag = CampaignTag("a" * CAMPAIGN_TAG_MAX_LENGTH)
    assert len(tag.value) == CAMPAIGN_TAG_MAX_LENGTH


# ---------- Campaign aggregate defaults ----------


@pytest.mark.unit
def test_campaign_dataclass_defaults_match_design_memo() -> None:
    """Genesis Campaign lands in PLANNED with empty sets + None optional fields."""
    campaign = Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
    )
    assert campaign.id == _CAMPAIGN_ID
    assert campaign.name.value == "test"
    assert campaign.intent == CampaignIntent.SERIES
    assert campaign.lead_actor_id == _LEAD_ACTOR_ID
    assert campaign.subject_id is None
    assert campaign.description is None
    assert campaign.tags == frozenset()
    assert campaign.external_refs == frozenset()
    assert campaign.external_id is None
    assert campaign.run_ids == frozenset()
    assert campaign.status == CampaignStatus.PLANNED
    assert campaign.last_status_reason is None


@pytest.mark.unit
def test_campaign_is_frozen() -> None:
    campaign = Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
    )
    with pytest.raises(AttributeError):
        campaign.id = UUID(int=0)  # type: ignore[misc]
