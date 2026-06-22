"""Bootstrap-time seed for the CampaignWatcher Agent.

The CampaignWatcher runtime (CORA's 9th seeded agent, a composition-root periodic
loop, deterministic flag-only) needs an Agent record (and its co-registered
Actor) at the pinned `CAMPAIGN_WATCHER_AGENT_ID` so it can author CampaignProgress
Decisions (`decided_by = ActorId(CAMPAIGN_WATCHER_AGENT_ID)`) as an agent-kind
principal. Mirrors `cora.agent.seed_procedure_watcher` except for the per-agent
constants; the shared scaffolding lives in `cora.agent._agent_seed`, and the
runtime mechanics in `cora.api._flag_watcher`.

Per [[project-campaign-watcher-design]]:
  - Pinned UUID in the `cab1` block (ninth seeded identity, sibling to
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, RunSupervisor
    `cccc00XX`, CautionPromoter `dddd00XX`, ClearanceExpirer `eeee00XX`,
    ClearanceWatcher `ffff00XX`, CalibrationWatcher `ca1100XX`, ProcedureWatcher
    `0c0c00XX`); deployment-stable forever. `cab1` is distinct from calibration's
    `ca11`.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template and a sentinel
    `ModelRef` (`provider="deterministic"`), never used to build an LLM (the
    runtime is a periodic staleness comparison over Held campaigns).
  - FLAG-ONLY: the runtime issues NO command. It records one
    Decision(context=CampaignProgress, choice=Stuck) per stuck-Held episode for a
    human to act on. Permission to record Decisions is granted at agent-definition
    time (the RunDebriefer stance); it issues no write command, though it does
    issue an authz-gated ListCampaigns read each tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CampaignWatcher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior CampaignWatcher-authored Decision
# (their actor_id pointers go stale). UUID is in the deployment-controlled
# `cab1` block (ninth seeded identity).
CAMPAIGN_WATCHER_AGENT_ID = UUID("01900000-0000-7000-8000-0000cab10010")
CAMPAIGN_WATCHER_AGENT_NAME = "CampaignWatcher"
CAMPAIGN_WATCHER_AGENT_KIND = "CampaignWatcher"
CAMPAIGN_WATCHER_AGENT_VERSION = "1.0.0"
CAMPAIGN_WATCHER_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: watches Held campaigns (operator-paused) and "
    "records one Decision(context=CampaignProgress, choice=Stuck) per campaign "
    "that has sat Held past the staleness window without being resumed or closed. "
    "Flag-only (advise a human); issues no command."
)


# Sentinel model ref: CampaignWatcher is rule-based, not an LLM agent. The Agent
# aggregate requires a ModelRef; this value is never used to build an LLM (the
# runtime is a periodic staleness comparison, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:CampaignWatcher:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000cab10012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000cab10013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000cab10014")


async def seed_campaign_watcher_agent(kernel: Kernel) -> None:
    """Seed the CampaignWatcher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CAMPAIGN_WATCHER_AGENT_ID,
        name=CAMPAIGN_WATCHER_AGENT_NAME,
        kind=CAMPAIGN_WATCHER_AGENT_KIND,
        version=CAMPAIGN_WATCHER_AGENT_VERSION,
        description=CAMPAIGN_WATCHER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCampaignWatcherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CAMPAIGN_WATCHER_AGENT_DESCRIPTION",
    "CAMPAIGN_WATCHER_AGENT_ID",
    "CAMPAIGN_WATCHER_AGENT_KIND",
    "CAMPAIGN_WATCHER_AGENT_NAME",
    "CAMPAIGN_WATCHER_AGENT_VERSION",
    "seed_campaign_watcher_agent",
]
