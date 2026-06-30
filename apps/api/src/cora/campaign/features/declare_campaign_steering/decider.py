"""Pure decider for the `DeclareCampaignSteering` command.

Multi-source guard: `{Planned, Active}`. PUT semantics (a re-declare
overwrites the prior intent; the evolver replaces both fields). Not a
lifecycle transition; status is untouched.

## Validation

  - State must not be None -> `CampaignNotFoundError`
  - Current status must be Planned | Active
    -> `CampaignCannotDeclareSteeringError`
  - Space must carry at least one axis -> `InvalidCampaignSteeringError`
  - A Satisfy objective must carry target_value + target_measurement_name
    -> `InvalidCampaignSteeringError`
"""

from datetime import datetime

from cora.campaign.aggregates.campaign import (
    Campaign,
    CampaignCannotDeclareSteeringError,
    CampaignNotFoundError,
    CampaignStatus,
    CampaignSteeringDeclared,
    InvalidCampaignSteeringError,
)
from cora.campaign.features.declare_campaign_steering.command import DeclareCampaignSteering
from cora.shared.steering import SteeringObjective, SteeringObjectiveKind

_STEERABLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
)


def _validate_objective(objective: SteeringObjective) -> None:
    """Reject an internally inconsistent objective.

    A Satisfy objective without a target_value or without a
    target_measurement_name cannot say what it is satisfying.
    """
    if objective.kind is SteeringObjectiveKind.SATISFY:
        if objective.target_value is None:
            raise InvalidCampaignSteeringError("a Satisfy objective requires a target_value")
        if objective.target_measurement_name is None:
            raise InvalidCampaignSteeringError(
                "a Satisfy objective requires a target_measurement_name"
            )


def decide(
    state: Campaign | None,
    command: DeclareCampaignSteering,
    *,
    now: datetime,
) -> list[CampaignSteeringDeclared]:
    """Decide the events produced by declaring a Campaign's steering intent.

    Invariants:
      - State must not be None -> CampaignNotFoundError
      - Current status must be Planned | Active
        -> CampaignCannotDeclareSteeringError
      - Space must carry >= 1 axis -> InvalidCampaignSteeringError
      - A Satisfy objective must carry target_value +
        target_measurement_name -> InvalidCampaignSteeringError
    """
    if state is None:
        raise CampaignNotFoundError(command.campaign_id)
    if state.status not in _STEERABLE_STATUSES:
        raise CampaignCannotDeclareSteeringError(state.id, state.status)

    if not command.space.axes:
        raise InvalidCampaignSteeringError("the search space must carry at least one axis")
    _validate_objective(command.objective)

    return [
        CampaignSteeringDeclared(
            campaign_id=state.id,
            objective=command.objective,
            space=command.space,
            occurred_at=now,
        )
    ]
