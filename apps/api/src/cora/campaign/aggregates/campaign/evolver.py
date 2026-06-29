"""Evolver: replay events to reconstruct Campaign state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `CampaignEvent` without a matching match arm here.

Status mapping per event type (8 arms across 6i-a + 6i-c):

  - `CampaignRegistered` -> PLANNED   (genesis; status implicit)
  - `CampaignStarted`    -> ACTIVE    (single-source: Planned only)
  - `CampaignHeld`       -> HELD      (single-source: Active only;
                              sets `last_status_reason`)
  - `CampaignResumed`    -> ACTIVE    (single-source: Held only;
                              preserves `last_status_reason` --
                              audit breadcrumb "why was it held
                              before the resume?" stays readable)
  - `CampaignClosed`     -> CLOSED    (multi-source: Active | Held)
  - `CampaignAbandoned`  -> ABANDONED (multi-source: Planned | Active |
                              Held; sets `last_status_reason`)
  - `CampaignRunAdded`   -> status preserved; unions run_id into run_ids
                              (membership mutation)
  - `CampaignRunRemoved` -> status preserved; removes run_id from run_ids
                              (reason on event is per-membership audit,
                              NOT last_status_reason)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.

Membership mutation arms preserve `status` and
`last_status_reason` (membership mutations are NOT status transitions
per design memo lock).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.campaign.aggregates.campaign.events import (
    CampaignAbandoned,
    CampaignClosed,
    CampaignEvent,
    CampaignHeld,
    CampaignRegistered,
    CampaignResumed,
    CampaignRunAdded,
    CampaignRunRemoved,
    CampaignStarted,
    CampaignSteeringDeclared,
)
from cora.campaign.aggregates.campaign.state import (
    Campaign,
    CampaignDescription,
    CampaignIntent,
    CampaignName,
    CampaignStatus,
    CampaignTag,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Campaign | None, event: CampaignEvent) -> Campaign:
    """Apply one event to the current state."""
    match event:
        case CampaignRegistered(
            campaign_id=campaign_id,
            name=name,
            intent=intent,
            lead_actor_id=lead_actor_id,
            subject_id=subject_id,
            description=description,
            tags=tags,
            external_refs=external_refs,
            external_id=external_id,
        ):
            _ = state  # CampaignRegistered is the genesis event; prior state ignored
            return Campaign(
                id=campaign_id,
                name=CampaignName(name),
                intent=CampaignIntent(intent),
                lead_actor_id=lead_actor_id,
                subject_id=subject_id,
                description=(CampaignDescription(description) if description is not None else None),
                tags=frozenset(CampaignTag(t) for t in tags),
                external_refs=external_refs,
                external_id=external_id,
                status=CampaignStatus.PLANNED,
            )
        case CampaignStarted():
            prior = require_state(state, "CampaignStarted")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ACTIVE,
                last_status_reason=prior.last_status_reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignHeld(reason=reason):
            prior = require_state(state, "CampaignHeld")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.HELD,
                last_status_reason=reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignResumed():
            prior = require_state(state, "CampaignResumed")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ACTIVE,
                last_status_reason=prior.last_status_reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignClosed():
            prior = require_state(state, "CampaignClosed")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.CLOSED,
                last_status_reason=prior.last_status_reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignAbandoned(reason=reason):
            prior = require_state(state, "CampaignAbandoned")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=CampaignStatus.ABANDONED,
                last_status_reason=reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignRunAdded(run_id=run_id):
            # membership add. Idempotency invariant is
            # enforced at the decider; the evolver trusts the event log
            # and unions the run_id into state.run_ids. Status NOT
            # touched -- membership is orthogonal to lifecycle.
            # last_status_reason preserved (membership mutations are
            # NOT status transitions per design memo lock).
            prior = require_state(state, "CampaignRunAdded")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids | {run_id},
                status=prior.status,
                last_status_reason=prior.last_status_reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignRunRemoved(run_id=run_id):
            # membership remove. Per design memo lock, the
            # `reason` on CampaignRunRemoved is a per-membership audit
            # breadcrumb (lives on the event payload only); it does NOT
            # populate last_status_reason (that field is for status
            # transitions only). The evolver removes the run_id from
            # state.run_ids and leaves status / last_status_reason
            # alone.
            prior = require_state(state, "CampaignRunRemoved")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids - {run_id},
                status=prior.status,
                last_status_reason=prior.last_status_reason,
                steering_objective=prior.steering_objective,
                steering_space=prior.steering_space,
            )
        case CampaignSteeringDeclared(objective=objective, space=space):
            # steering-intent declaration. PUT semantics: the
            # objective + space replace any prior declared intent
            # wholesale. Status / last_status_reason / run_ids are
            # preserved (declaring where a future across-Run steerer may
            # look is orthogonal to lifecycle and membership).
            prior = require_state(state, "CampaignSteeringDeclared")
            return Campaign(
                id=prior.id,
                name=prior.name,
                intent=prior.intent,
                lead_actor_id=prior.lead_actor_id,
                subject_id=prior.subject_id,
                description=prior.description,
                tags=prior.tags,
                external_refs=prior.external_refs,
                external_id=prior.external_id,
                run_ids=prior.run_ids,
                status=prior.status,
                last_status_reason=prior.last_status_reason,
                steering_objective=objective,
                steering_space=space,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CampaignEvent]) -> Campaign | None:
    """Replay a stream of events from the empty initial state."""
    state: Campaign | None = None
    for event in events:
        state = evolve(state, event)
    return state
