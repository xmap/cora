"""Evolver arms: genesis + 5 transitions + require_state on empty."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignAbandoned,
    CampaignClosed,
    CampaignDescription,
    CampaignHeld,
    CampaignIntent,
    CampaignName,
    CampaignRegistered,
    CampaignResumed,
    CampaignStarted,
    CampaignStatus,
    CampaignTag,
    evolve,
    fold,
)
from cora.shared.identifier import Identifier

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-00000000e001")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000e002")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000e003")


def _registered() -> CampaignRegistered:
    return CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="In-situ heating",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=_SUBJECT_ID,
        description="long-form description",
        tags=frozenset({"battery", "heating"}),
        external_refs=frozenset({Identifier(scheme="proposal", value="2025-100")}),
        external_id=None,
        occurred_at=_NOW,
    )


# ---------- CampaignRegistered genesis ----------


@pytest.mark.unit
def test_registered_creates_planned_campaign() -> None:
    state = evolve(None, _registered())
    assert state.id == _CAMPAIGN_ID
    assert state.name == CampaignName("In-situ heating")
    assert state.intent == CampaignIntent.SERIES
    assert state.lead_actor_id == _LEAD_ACTOR_ID
    assert state.subject_id == _SUBJECT_ID
    assert state.description == CampaignDescription("long-form description")
    assert state.tags == frozenset({CampaignTag("battery"), CampaignTag("heating")})
    assert state.external_refs == frozenset({Identifier(scheme="proposal", value="2025-100")})
    assert state.external_id is None
    assert state.run_ids == frozenset()
    assert state.status == CampaignStatus.PLANNED
    assert state.last_status_reason is None


@pytest.mark.unit
def test_registered_with_no_description_yields_none() -> None:
    event = CampaignRegistered(
        campaign_id=_CAMPAIGN_ID,
        name="x",
        intent="Series",
        lead_actor_id=_LEAD_ACTOR_ID,
        subject_id=None,
        description=None,
        tags=frozenset(),
        external_refs=frozenset(),
        external_id=None,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.description is None


@pytest.mark.unit
def test_registered_overrides_prior_state() -> None:
    """Genesis event ignores any prior state (defensive)."""
    prior = Campaign(
        id=UUID(int=99),
        name=CampaignName("stale"),
        intent=CampaignIntent.SWEEP,
        lead_actor_id=UUID(int=11),
    )
    state = evolve(prior, _registered())
    assert state.id == _CAMPAIGN_ID
    assert state.intent == CampaignIntent.SERIES


# ---------- CampaignStarted ----------


@pytest.mark.unit
def test_started_transitions_planned_to_active() -> None:
    state = fold([_registered(), CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW)])
    assert state is not None
    assert state.status == CampaignStatus.ACTIVE
    assert state.last_status_reason is None


@pytest.mark.unit
def test_started_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(None, CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW))


# ---------- CampaignHeld ----------


@pytest.mark.unit
def test_held_transitions_to_held_with_reason() -> None:
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(
                campaign_id=_CAMPAIGN_ID,
                reason="beam interruption",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.HELD
    assert state.last_status_reason == "beam interruption"


@pytest.mark.unit
def test_held_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(
            None,
            CampaignHeld(campaign_id=_CAMPAIGN_ID, reason="x", occurred_at=_NOW),
        )


# ---------- CampaignResumed ----------


@pytest.mark.unit
def test_resumed_transitions_held_to_active_and_preserves_reason() -> None:
    """Resume preserves last_status_reason (audit breadcrumb)."""
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(
                campaign_id=_CAMPAIGN_ID,
                reason="beam interruption",
                occurred_at=_NOW,
            ),
            CampaignResumed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.ACTIVE
    assert state.last_status_reason == "beam interruption"


@pytest.mark.unit
def test_resumed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(None, CampaignResumed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW))


# ---------- CampaignClosed ----------


@pytest.mark.unit
def test_closed_from_active_transitions_to_closed() -> None:
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignClosed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.CLOSED


@pytest.mark.unit
def test_closed_from_held_transitions_to_closed() -> None:
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(campaign_id=_CAMPAIGN_ID, reason="x", occurred_at=_NOW),
            CampaignClosed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.CLOSED
    # last_status_reason preserved from the Held event
    assert state.last_status_reason == "x"


@pytest.mark.unit
def test_closed_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(None, CampaignClosed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW))


# ---------- CampaignAbandoned ----------


@pytest.mark.unit
def test_abandoned_transitions_to_abandoned_with_reason() -> None:
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignAbandoned(
                campaign_id=_CAMPAIGN_ID,
                reason="instrument failure",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.ABANDONED
    assert state.last_status_reason == "instrument failure"


@pytest.mark.unit
def test_abandoned_from_planned_transitions_to_abandoned() -> None:
    """Multi-source: Planned can abandon directly."""
    state = fold(
        [
            _registered(),
            CampaignAbandoned(
                campaign_id=_CAMPAIGN_ID,
                reason="proposal cancelled",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.status == CampaignStatus.ABANDONED


@pytest.mark.unit
def test_abandoned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError):
        evolve(
            None,
            CampaignAbandoned(campaign_id=_CAMPAIGN_ID, reason="x", occurred_at=_NOW),
        )


# ---------- fold ----------


@pytest.mark.unit
def test_fold_empty_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_preserves_run_ids_empty_through_lifecycle() -> None:
    """6i-a: run_ids stays empty across all transition arms."""
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(campaign_id=_CAMPAIGN_ID, reason="r", occurred_at=_NOW),
            CampaignResumed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignClosed(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.run_ids == frozenset()


# ---------- CampaignRunAdded / CampaignRunRemoved arms ----------


@pytest.mark.unit
def test_run_added_unions_run_id_into_run_ids() -> None:
    from cora.campaign.aggregates.campaign import CampaignRunAdded

    run_id = UUID("01900000-0000-7000-8000-0000000000aa")
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignRunAdded(campaign_id=_CAMPAIGN_ID, run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.run_ids == frozenset({run_id})
    # Status preserved -- membership is orthogonal to lifecycle.
    assert state.status == CampaignStatus.ACTIVE


@pytest.mark.unit
def test_run_added_preserves_last_status_reason() -> None:
    """Membership mutations are NOT status transitions per design memo
    lock. last_status_reason must survive the run_ids mutation."""
    from cora.campaign.aggregates.campaign import CampaignRunAdded

    run_id = UUID("01900000-0000-7000-8000-0000000000ab")
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(
                campaign_id=_CAMPAIGN_ID,
                reason="beam interruption",
                occurred_at=_NOW,
            ),
            CampaignRunAdded(campaign_id=_CAMPAIGN_ID, run_id=run_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.last_status_reason == "beam interruption"
    assert state.status == CampaignStatus.HELD


@pytest.mark.unit
def test_run_added_on_empty_state_raises() -> None:
    from cora.campaign.aggregates.campaign import CampaignRunAdded

    with pytest.raises(ValueError):
        evolve(
            None,
            CampaignRunAdded(
                campaign_id=_CAMPAIGN_ID,
                run_id=UUID("01900000-0000-7000-8000-0000000000ac"),
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_run_removed_removes_run_id_from_run_ids() -> None:
    from cora.campaign.aggregates.campaign import CampaignRunAdded, CampaignRunRemoved

    run_id = UUID("01900000-0000-7000-8000-0000000000ad")
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignRunAdded(campaign_id=_CAMPAIGN_ID, run_id=run_id, occurred_at=_NOW),
            CampaignRunRemoved(
                campaign_id=_CAMPAIGN_ID,
                run_id=run_id,
                reason="reassigned",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.run_ids == frozenset()
    assert state.status == CampaignStatus.ACTIVE


@pytest.mark.unit
def test_run_removed_does_not_update_last_status_reason() -> None:
    """Design memo lock: CampaignRunRemoved.reason is per-membership
    audit (event payload only). It does NOT populate
    last_status_reason (that field is for status transitions only)."""
    from cora.campaign.aggregates.campaign import CampaignRunAdded, CampaignRunRemoved

    run_id = UUID("01900000-0000-7000-8000-0000000000ae")
    state = fold(
        [
            _registered(),
            CampaignStarted(campaign_id=_CAMPAIGN_ID, occurred_at=_NOW),
            CampaignHeld(
                campaign_id=_CAMPAIGN_ID,
                reason="beam interruption",
                occurred_at=_NOW,
            ),
            CampaignRunAdded(campaign_id=_CAMPAIGN_ID, run_id=run_id, occurred_at=_NOW),
            CampaignRunRemoved(
                campaign_id=_CAMPAIGN_ID,
                run_id=run_id,
                reason="reassigned",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    # last_status_reason still carries the Held event's reason, NOT
    # the remove's reason.
    assert state.last_status_reason == "beam interruption"


@pytest.mark.unit
def test_run_removed_on_empty_state_raises() -> None:
    from cora.campaign.aggregates.campaign import CampaignRunRemoved

    with pytest.raises(ValueError):
        evolve(
            None,
            CampaignRunRemoved(
                campaign_id=_CAMPAIGN_ID,
                run_id=UUID("01900000-0000-7000-8000-0000000000af"),
                reason="x",
                occurred_at=_NOW,
            ),
        )
