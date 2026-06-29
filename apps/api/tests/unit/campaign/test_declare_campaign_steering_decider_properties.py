"""Property-based tests for `declare_campaign_steering.decide` (Campaign BC).

Complements the example-based `test_declare_campaign_steering_decider.py` with
universal claims across generated inputs. The decider is a pure declaration
guard (NOT a lifecycle transition)

    (state, command, now) -> list[CampaignSteeringDeclared]

Load-bearing properties:

  - state=None always raises `CampaignNotFoundError` carrying
    command.campaign_id.
  - The source-state partition is total over `CampaignStatus`: only
    `Planned` / `Active` emit one `CampaignSteeringDeclared`; every other
    status raises `CampaignCannotDeclareSteeringError` carrying the current
    status (the status guard runs before objective/space validation).
  - The emitted event's campaign_id is `state.id`, never command.campaign_id,
    and carries the command's objective + space verbatim.
  - A Satisfy objective missing target_value raises `InvalidCampaignSteeringError`.
  - Pure: same (state, command, now) returns equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

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
from cora.campaign.features import declare_campaign_steering
from cora.campaign.features.declare_campaign_steering import DeclareCampaignSteering
from cora.shared.steering import (
    SteeringAxis,
    SteeringObjective,
    SteeringObjectiveKind,
    SteeringSpace,
)
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_LEAD_ACTOR_ID = UUID(int=5)

_DECLARABLE_SOURCES = (CampaignStatus.PLANNED, CampaignStatus.ACTIVE)
_DISALLOWED_SOURCES = tuple(s for s in CampaignStatus if s not in frozenset(_DECLARABLE_SOURCES))

_OBJECTIVE = SteeringObjective(kind=SteeringObjectiveKind.MINIMIZE, target_measurement_name="m")
_SPACE = SteeringSpace(axes=(SteeringAxis(name="theta", lower=-5.0, upper=5.0),))


def _campaign(*, campaign_id: UUID, status: CampaignStatus) -> Campaign:
    return Campaign(
        id=campaign_id,
        name=CampaignName("Beamtime 2026-1"),
        intent=CampaignIntent.SWEEP,
        lead_actor_id=_LEAD_ACTOR_ID,
        status=status,
    )


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_declare_with_none_state_always_raises_not_found(
    campaign_id: UUID,
    now: datetime,
) -> None:
    """Empty stream always raises `CampaignNotFoundError` carrying command.campaign_id."""
    with pytest.raises(CampaignNotFoundError) as exc:
        declare_campaign_steering.decide(
            state=None,
            command=DeclareCampaignSteering(
                campaign_id=campaign_id, objective=_OBJECTIVE, space=_SPACE
            ),
            now=now,
        )
    assert exc.value.campaign_id == campaign_id


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DECLARABLE_SOURCES),
    now=aware_datetimes(),
)
def test_declare_from_planned_or_active_emits_single_event(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Planned / Active are the declarable sources; emit one event carrying objective+space."""
    events = declare_campaign_steering.decide(
        state=_campaign(campaign_id=campaign_id, status=source),
        command=DeclareCampaignSteering(
            campaign_id=campaign_id, objective=_OBJECTIVE, space=_SPACE
        ),
        now=now,
    )
    assert events == [
        CampaignSteeringDeclared(
            campaign_id=campaign_id,
            objective=_OBJECTIVE,
            space=_SPACE,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    campaign_id=st.uuids(),
    source=st.sampled_from(_DISALLOWED_SOURCES),
    now=aware_datetimes(),
)
def test_declare_from_disallowed_source_always_raises_cannot_declare(
    campaign_id: UUID,
    source: CampaignStatus,
    now: datetime,
) -> None:
    """Any source other than Planned/Active raises, carrying the current status."""
    with pytest.raises(CampaignCannotDeclareSteeringError) as exc:
        declare_campaign_steering.decide(
            state=_campaign(campaign_id=campaign_id, status=source),
            command=DeclareCampaignSteering(
                campaign_id=campaign_id, objective=_OBJECTIVE, space=_SPACE
            ),
            now=now,
        )
    assert exc.value.current_status is source


@pytest.mark.unit
@given(
    state_campaign_id=st.uuids(),
    command_campaign_id=st.uuids(),
    now=aware_datetimes(),
)
def test_declare_uses_state_id_not_command_campaign_id(
    state_campaign_id: UUID,
    command_campaign_id: UUID,
    now: datetime,
) -> None:
    """The emitted event's campaign_id is state.id, not command.campaign_id."""
    assume(state_campaign_id != command_campaign_id)
    events = declare_campaign_steering.decide(
        state=_campaign(campaign_id=state_campaign_id, status=CampaignStatus.PLANNED),
        command=DeclareCampaignSteering(
            campaign_id=command_campaign_id, objective=_OBJECTIVE, space=_SPACE
        ),
        now=now,
    )
    assert events[0].campaign_id == state_campaign_id


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_declare_satisfy_without_target_value_raises_invalid(
    campaign_id: UUID,
    now: datetime,
) -> None:
    """A Satisfy objective with no target_value is rejected on a declarable source."""
    with pytest.raises(InvalidCampaignSteeringError):
        declare_campaign_steering.decide(
            state=_campaign(campaign_id=campaign_id, status=CampaignStatus.PLANNED),
            command=DeclareCampaignSteering(
                campaign_id=campaign_id,
                objective=SteeringObjective(
                    kind=SteeringObjectiveKind.SATISFY, target_measurement_name="m"
                ),
                space=_SPACE,
            ),
            now=now,
        )


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_declare_empty_space_raises_invalid(
    campaign_id: UUID,
    now: datetime,
) -> None:
    """A space with no axes is rejected on a declarable source."""
    with pytest.raises(InvalidCampaignSteeringError):
        declare_campaign_steering.decide(
            state=_campaign(campaign_id=campaign_id, status=CampaignStatus.PLANNED),
            command=DeclareCampaignSteering(
                campaign_id=campaign_id, objective=_OBJECTIVE, space=SteeringSpace(axes=())
            ),
            now=now,
        )


@pytest.mark.unit
@given(campaign_id=st.uuids(), now=aware_datetimes())
def test_declare_is_pure_same_input_same_output(
    campaign_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal events (no clock leakage)."""
    state = _campaign(campaign_id=campaign_id, status=CampaignStatus.ACTIVE)
    command = DeclareCampaignSteering(campaign_id=campaign_id, objective=_OBJECTIVE, space=_SPACE)
    first = declare_campaign_steering.decide(state=state, command=command, now=now)
    second = declare_campaign_steering.decide(state=state, command=command, now=now)
    assert first == second
