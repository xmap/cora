"""Bootstrap-time seed for the ClearanceWatcher Agent.

The ClearanceWatcher runtime (CORA's 4th ACTIVE agent and first pure flag-only
/ advise-a-human agent, a composition-root periodic loop) needs an Agent record
(and its co-registered Actor) at the pinned `CLEARANCE_WATCHER_AGENT_ID` so it
can author ClearanceProgress Decisions
(`decided_by = ActorId(CLEARANCE_WATCHER_AGENT_ID)`) as an agent-kind
principal. Mirrors `cora.agent.seed_clearance_expirer` except for the per-agent
constants; the shared scaffolding lives in `cora.agent._agent_seed`.

Per [[project-clearance-watcher-design]]:
  - Pinned UUID in the `ffff00XX` range (sixth seeded identity, sibling to
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, RunSupervisor
    `cccc00XX`, CautionPromoter `dddd00XX`, ClearanceExpirer `eeee00XX`);
    deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`), never used to build an LLM (the runtime is a
    periodic loop applying a staleness clock comparison).
  - FLAG-ONLY: the runtime issues NO command. It records one
    Decision(context=ClearanceProgress, choice=Flag) per stall episode for a
    human to act on. Permission to record Decisions is granted at
    agent-definition time (the RunDebriefer stance); there is no
    authorized-command leg and so no per-command Policy grant to seed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# ClearanceWatcher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior ClearanceWatcher-authored Decision
# (their actor_id pointers go stale). UUID is in the deployment-controlled
# `ffff00XX` range (sixth seeded identity).
CLEARANCE_WATCHER_AGENT_ID = UUID("01900000-0000-7000-8000-0000ffff0010")
CLEARANCE_WATCHER_AGENT_NAME = "ClearanceWatcher"
CLEARANCE_WATCHER_AGENT_KIND = "ClearanceWatcher"
CLEARANCE_WATCHER_AGENT_VERSION = "1.0.0"
CLEARANCE_WATCHER_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: watches the front of the safety-Clearance "
    "lifecycle (Submitted/UnderReview/Approved) and records one "
    "Decision(context=ClearanceProgress) per stalled clearance that has sat "
    "past the staleness window without progressing toward Active. Flag-only "
    "(advise a human); issues no command."
)


# Sentinel model ref: ClearanceWatcher is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an LLM
# (the runtime is a periodic staleness comparison, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:ClearanceWatcher:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000ffff0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000ffff0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000ffff0014")


async def seed_clearance_watcher_agent(kernel: Kernel) -> None:
    """Seed the ClearanceWatcher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CLEARANCE_WATCHER_AGENT_ID,
        name=CLEARANCE_WATCHER_AGENT_NAME,
        kind=CLEARANCE_WATCHER_AGENT_KIND,
        version=CLEARANCE_WATCHER_AGENT_VERSION,
        description=CLEARANCE_WATCHER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedClearanceWatcherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CLEARANCE_WATCHER_AGENT_DESCRIPTION",
    "CLEARANCE_WATCHER_AGENT_ID",
    "CLEARANCE_WATCHER_AGENT_KIND",
    "CLEARANCE_WATCHER_AGENT_NAME",
    "CLEARANCE_WATCHER_AGENT_VERSION",
    "seed_clearance_watcher_agent",
]
