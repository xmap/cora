"""Decider tests for `declare_campaign_steering` slice.

Multi-source from Planned | Active; PUT semantics; rejects Held /
Closed / Abandoned, an empty space, and a Satisfy objective missing its
target_value / target_measurement_name.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotDeclareSteeringError,
    CampaignIntent,
    CampaignName,
    CampaignNotFoundError,
    CampaignStatus,
    CampaignSteeringDeclared,
    InvalidCampaignSteeringError,
)
from cora.campaign.features.declare_campaign_steering import DeclareCampaignSteering
from cora.campaign.features.declare_campaign_steering.decider import decide
from cora.shared.steering import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-0000000d5001")
_LEAD = UUID("01900000-0000-7000-8000-0000000d5099")


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=_CAMPAIGN_ID,
        name=CampaignName("test"),
        intent=CampaignIntent.SWEEP,
        lead_actor_id=_LEAD,
        status=status,
    )


def _space() -> SteeringSpace:
    return SteeringSpace(axes=(SteeringAxis(name="temperature", lower=300.0, upper=900.0),))


def _maximize() -> SteeringObjective:
    return SteeringObjective(kind=SteeringObjectiveKind.MAXIMIZE, target_measurement_name="yield")


def _command(objective: SteeringObjective, space: SteeringSpace) -> DeclareCampaignSteering:
    return DeclareCampaignSteering(campaign_id=_CAMPAIGN_ID, objective=objective, space=space)


@pytest.mark.unit
def test_decider_emits_steering_declared_when_planned() -> None:
    events = decide(
        state=_campaign(CampaignStatus.PLANNED),
        command=_command(_maximize(), _space()),
        now=_NOW,
    )
    assert len(events) == 1
    [event] = events
    assert isinstance(event, CampaignSteeringDeclared)
    assert event.objective == _maximize()
    assert event.space == _space()
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decider_emits_steering_declared_when_active() -> None:
    events = decide(
        state=_campaign(CampaignStatus.ACTIVE),
        command=_command(_maximize(), _space()),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], CampaignSteeringDeclared)


@pytest.mark.unit
def test_decider_accepts_satisfy_objective_with_target() -> None:
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name="resolution",
        target_value=1.5,
    )
    events = decide(
        state=_campaign(CampaignStatus.ACTIVE),
        command=_command(objective, _space()),
        now=_NOW,
    )
    assert events[0].objective == objective


@pytest.mark.unit
def test_decider_raises_not_found_on_empty_state() -> None:
    with pytest.raises(CampaignNotFoundError):
        decide(
            state=None,
            command=_command(_maximize(), _space()),
            now=_NOW,
        )


@pytest.mark.parametrize(
    "current_status",
    [
        CampaignStatus.HELD,
        CampaignStatus.CLOSED,
        CampaignStatus.ABANDONED,
    ],
)
@pytest.mark.unit
def test_decider_rejects_non_steerable_statuses(current_status: CampaignStatus) -> None:
    with pytest.raises(CampaignCannotDeclareSteeringError) as exc_info:
        decide(
            state=_campaign(current_status),
            command=_command(_maximize(), _space()),
            now=_NOW,
        )
    assert exc_info.value.current_status == current_status


@pytest.mark.unit
def test_decider_rejects_empty_space() -> None:
    with pytest.raises(InvalidCampaignSteeringError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=_command(_maximize(), SteeringSpace(axes=())),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_rejects_satisfy_without_target_value() -> None:
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name="resolution",
        target_value=None,
    )
    with pytest.raises(InvalidCampaignSteeringError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=_command(objective, _space()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decider_rejects_satisfy_without_target_measurement_name() -> None:
    objective = SteeringObjective(
        kind=SteeringObjectiveKind.SATISFY,
        target_measurement_name=None,
        target_value=1.5,
    )
    with pytest.raises(InvalidCampaignSteeringError):
        decide(
            state=_campaign(CampaignStatus.ACTIVE),
            command=_command(objective, _space()),
            now=_NOW,
        )
