"""Decider-purity tests for `register_campaign` slice."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignAlreadyExistsError,
    CampaignIntent,
    CampaignName,
    CampaignRegistered,
    InvalidCampaignDescriptionError,
    InvalidCampaignExternalIdError,
    InvalidCampaignNameError,
    InvalidCampaignTagError,
)
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.register_campaign.decider import decide
from cora.shared.identifier import Identifier, InvalidIdentifierError

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000d001")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000d099")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000d003")


def _command(**overrides: object) -> RegisterCampaign:
    base: dict[str, object] = {
        "name": "In-situ heating series #42",
        "intent": CampaignIntent.SERIES,
        "lead_actor_id": _LEAD_ACTOR_ID,
    }
    base.update(overrides)
    return RegisterCampaign(**base)  # type: ignore[arg-type]


# ---------- happy path ----------


@pytest.mark.unit
def test_decider_emits_registered_event_for_minimal_command() -> None:
    events = decide(state=None, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignRegistered)
    assert event.campaign_id == _NEW_ID
    assert event.name == "In-situ heating series #42"
    assert event.intent == "Series"
    assert event.lead_actor_id == _LEAD_ACTOR_ID
    assert event.subject_id is None
    assert event.description is None
    assert event.tags == frozenset()
    assert event.external_refs == frozenset()
    assert event.external_id is None
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_trims_name() -> None:
    events = decide(
        state=None,
        command=_command(name="  trimmed  "),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].name == "trimmed"


@pytest.mark.unit
def test_decider_carries_subject_id() -> None:
    events = decide(
        state=None,
        command=_command(subject_id=_SUBJECT_ID),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].subject_id == _SUBJECT_ID


@pytest.mark.unit
def test_decider_trims_description_when_provided() -> None:
    events = decide(
        state=None,
        command=_command(description="  full description here  "),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].description == "full description here"


@pytest.mark.unit
def test_decider_omitted_description_yields_none_on_event() -> None:
    events = decide(state=None, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert events[0].description is None


@pytest.mark.unit
def test_decider_normalizes_tags_via_vo() -> None:
    events = decide(
        state=None,
        command=_command(tags=frozenset({"  battery  ", "heating"})),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].tags == frozenset({"battery", "heating"})


@pytest.mark.unit
def test_decider_carries_external_refs() -> None:
    refs = frozenset({Identifier(scheme="proposal", value="2025-100")})
    events = decide(
        state=None,
        command=_command(external_refs=refs),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].external_refs == refs


@pytest.mark.unit
def test_decider_trims_external_id_when_provided() -> None:
    events = decide(
        state=None,
        command=_command(external_id="  DOI:10.1234/abc  "),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].external_id == "DOI:10.1234/abc"


@pytest.mark.unit
def test_decider_passes_through_lead_actor_id_even_when_different_from_principal() -> None:
    """Campaign keeps `lead_actor_id` on the command surface (LIMS Study
    Director precedent); decider trusts the command's value rather than
    deriving from envelope. This is the explicit anti-hook on closing
    the lead_actor_id surface."""
    other_lead = UUID("01900000-0000-7000-8000-00000000dabc")
    events = decide(
        state=None,
        command=_command(lead_actor_id=other_lead),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].lead_actor_id == other_lead


# ---------- already-exists ----------


@pytest.mark.unit
def test_decider_rejects_when_campaign_already_exists() -> None:
    existing = Campaign(
        id=_NEW_ID,
        name=CampaignName("existing"),
        intent=CampaignIntent.SERIES,
        lead_actor_id=_LEAD_ACTOR_ID,
    )
    with pytest.raises(CampaignAlreadyExistsError) as exc_info:
        decide(state=existing, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert exc_info.value.campaign_id == _NEW_ID


# ---------- field-by-field validation ----------


@pytest.mark.unit
def test_decider_rejects_empty_name() -> None:
    with pytest.raises(InvalidCampaignNameError):
        decide(state=None, command=_command(name="   "), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_decider_rejects_empty_description_when_provided() -> None:
    with pytest.raises(InvalidCampaignDescriptionError):
        decide(
            state=None,
            command=_command(description="   "),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_decider_rejects_empty_tag() -> None:
    with pytest.raises(InvalidCampaignTagError):
        decide(
            state=None,
            command=_command(tags=frozenset({"valid", "   "})),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_decider_rejects_empty_external_id_when_provided() -> None:
    with pytest.raises(InvalidCampaignExternalIdError):
        decide(
            state=None,
            command=_command(external_id="   "),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_decider_rejects_too_long_external_id() -> None:
    with pytest.raises(InvalidCampaignExternalIdError):
        decide(
            state=None,
            command=_command(external_id="a" * 101),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_external_ref_vo_rejects_empty_scheme() -> None:
    """The Identifier VO raises at command-build time; the decider
    never sees a malformed ref."""
    with pytest.raises(InvalidIdentifierError):
        Identifier(scheme="", value="abc")
