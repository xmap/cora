"""Bootstrap-time seed for the CalibrationWatcher Agent.

The CalibrationWatcher runtime (CORA's 7th seeded agent, a composition-root
periodic loop, deterministic flag-only) needs an Agent record (and its
co-registered Actor) at the pinned `CALIBRATION_WATCHER_AGENT_ID` so it can
author CalibrationVerification Decisions
(`decided_by = ActorId(CALIBRATION_WATCHER_AGENT_ID)`) as an agent-kind
principal. Mirrors `cora.agent.seed_clearance_watcher` except for the per-agent
constants; the shared scaffolding lives in `cora.agent._agent_seed`.

Per [[project-calibration-watcher-design]]:
  - Pinned UUID in the `ca11` block (seventh seeded identity, sibling to
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, RunSupervisor
    `cccc00XX`, CautionPromoter `dddd00XX`, ClearanceExpirer `eeee00XX`,
    ClearanceWatcher `ffff00XX`); deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template and a sentinel
    `ModelRef` (`provider="deterministic"`), never used to build an LLM (the
    runtime is a periodic staleness comparison).
  - FLAG-ONLY: the runtime issues NO write command. It records one
    Decision(context=CalibrationVerification, choice=Stale) per stale-calibration
    episode for a human to act on. Permission to record Decisions is granted at
    agent-definition time (the RunDebriefer stance); there is no write-command leg
    and so no per-command Policy grant to seed, though it does issue an
    authz-gated ListCalibrations read each tick (under a real Authorize policy the
    agent principal needs that read grant or the drain is denied).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CalibrationWatcher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior CalibrationWatcher-authored Decision
# (their actor_id pointers go stale). UUID is in the deployment-controlled
# `ca11` block (seventh seeded identity).
CALIBRATION_WATCHER_AGENT_ID = UUID("01900000-0000-7000-8000-0000ca110010")
CALIBRATION_WATCHER_AGENT_NAME = "CalibrationWatcher"
CALIBRATION_WATCHER_AGENT_KIND = "CalibrationWatcher"
CALIBRATION_WATCHER_AGENT_VERSION = "1.0.0"
CALIBRATION_WATCHER_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: watches the calibration-verification lifecycle "
    "and records one Decision(context=CalibrationVerification, choice=Stale) per "
    "Provisional calibration whose newest revision has sat unverified past the "
    "staleness window. Flag-only (advise a human); issues no command."
)


# Sentinel model ref: CalibrationWatcher is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an LLM
# (the runtime is a periodic staleness comparison, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:CalibrationWatcher:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000ca110012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000ca110013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000ca110014")


async def seed_calibration_watcher_agent(kernel: Kernel) -> None:
    """Seed the CalibrationWatcher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=CALIBRATION_WATCHER_AGENT_ID,
        name=CALIBRATION_WATCHER_AGENT_NAME,
        kind=CALIBRATION_WATCHER_AGENT_KIND,
        version=CALIBRATION_WATCHER_AGENT_VERSION,
        description=CALIBRATION_WATCHER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedCalibrationWatcherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "CALIBRATION_WATCHER_AGENT_DESCRIPTION",
    "CALIBRATION_WATCHER_AGENT_ID",
    "CALIBRATION_WATCHER_AGENT_KIND",
    "CALIBRATION_WATCHER_AGENT_NAME",
    "CALIBRATION_WATCHER_AGENT_VERSION",
    "seed_calibration_watcher_agent",
]
