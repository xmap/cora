"""Compose the Campaign BC's handlers from `Kernel`.

`wire_campaign(deps)` is invoked once from the FastAPI lifespan and
the returned `CampaignHandlers` bundle is stored on
`app.state.campaign`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `CampaignHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Supply / Safety / Caution:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers (6i-a + 6i-b)

  - `register_campaign` (create-style; idempotency-wrapped)
  - `start_campaign`    (transition; no idempotency wrap)
  - `hold_campaign`     (transition; no idempotency wrap)
  - `resume_campaign`   (transition; no idempotency wrap)
  - `close_campaign`    (transition; no idempotency wrap)
  - `abandon_campaign`  (transition; no idempotency wrap)
  - `get_campaign`      (query; fold-on-read)
  - `list_campaigns`    (query; projection-backed; 6i-b)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.campaign.features import (
    abandon_campaign,
    add_run_to_campaign,
    close_campaign,
    declare_campaign_steering,
    get_campaign,
    hold_campaign,
    list_campaigns,
    register_campaign,
    remove_run_from_campaign,
    resume_campaign,
    start_campaign,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "campaign"


@dataclass(frozen=True)
class CampaignHandlers:
    """The Campaign BC's handler bundle, each closed over Kernel."""

    register_campaign: register_campaign.IdempotentHandler
    start_campaign: start_campaign.Handler
    hold_campaign: hold_campaign.Handler
    resume_campaign: resume_campaign.Handler
    close_campaign: close_campaign.Handler
    abandon_campaign: abandon_campaign.Handler
    add_run_to_campaign: add_run_to_campaign.Handler
    remove_run_from_campaign: remove_run_from_campaign.Handler
    declare_campaign_steering: declare_campaign_steering.Handler
    get_campaign: get_campaign.Handler
    list_campaigns: list_campaigns.Handler


def wire_campaign(deps: Kernel) -> CampaignHandlers:
    """Build the Campaign BC handlers from shared dependencies."""
    return CampaignHandlers(
        register_campaign=with_tracing(
            with_idempotency(
                register_campaign.bind(deps),
                deps.idempotency_store,
                command_name="RegisterCampaign",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterCampaign",
            bc=_BC,
        ),
        start_campaign=with_tracing(
            start_campaign.bind(deps),
            command_name="StartCampaign",
            bc=_BC,
        ),
        hold_campaign=with_tracing(
            hold_campaign.bind(deps),
            command_name="HoldCampaign",
            bc=_BC,
        ),
        resume_campaign=with_tracing(
            resume_campaign.bind(deps),
            command_name="ResumeCampaign",
            bc=_BC,
        ),
        close_campaign=with_tracing(
            close_campaign.bind(deps),
            command_name="CloseCampaign",
            bc=_BC,
        ),
        abandon_campaign=with_tracing(
            abandon_campaign.bind(deps),
            command_name="AbandonCampaign",
            bc=_BC,
        ),
        add_run_to_campaign=with_tracing(
            add_run_to_campaign.bind(deps),
            command_name="AddRunToCampaign",
            bc=_BC,
        ),
        remove_run_from_campaign=with_tracing(
            remove_run_from_campaign.bind(deps),
            command_name="RemoveRunFromCampaign",
            bc=_BC,
        ),
        declare_campaign_steering=with_tracing(
            declare_campaign_steering.bind(deps),
            command_name="DeclareCampaignSteering",
            bc=_BC,
        ),
        get_campaign=with_tracing(
            get_campaign.bind(deps),
            command_name="GetCampaign",
            bc=_BC,
            kind="query",
        ),
        list_campaigns=with_tracing(
            list_campaigns.bind(deps),
            command_name="ListCampaigns",
            bc=_BC,
            kind="query",
        ),
    )
