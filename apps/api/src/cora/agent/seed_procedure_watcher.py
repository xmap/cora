"""Bootstrap-time seed for the ProcedureWatcher Agent.

The ProcedureWatcher runtime (CORA's 8th seeded agent, a composition-root
periodic loop, deterministic flag-only) needs an Agent record (and its
co-registered Actor) at the pinned `PROCEDURE_WATCHER_AGENT_ID` so it can author
ProcedureProgress Decisions (`decided_by = ActorId(PROCEDURE_WATCHER_AGENT_ID)`)
as an agent-kind principal. Mirrors `cora.agent.seed_calibration_watcher` except
for the per-agent constants; the shared scaffolding lives in
`cora.agent._agent_seed`.

Per [[project-procedure-watcher-design]]:
  - Pinned UUID in the `0c0c` block (eighth seeded identity, sibling to
    RunDebriefer `aaaa00XX`, CautionDrafter `bbbb00XX`, RunSupervisor
    `cccc00XX`, CautionPromoter `dddd00XX`, ClearanceExpirer `eeee00XX`,
    ClearanceWatcher `ffff00XX`, CalibrationWatcher `ca1100XX`);
    deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template and a sentinel
    `ModelRef` (`provider="deterministic"`), never used to build an LLM (the
    runtime is a periodic staleness comparison over in-conduct procedures).
  - FLAG-ONLY: the runtime issues NO write command (unlike ClearanceExpirer's
    expire_clearance), so there is no per-command Policy grant to seed. It does
    issue an authz-gated `ListProcedures` read each tick, so under a real
    Authorize policy (not the dev AllowAllAuthorize) the agent principal still
    needs that read grant or every drain is denied; it records one
    Decision(context=ProcedureProgress, choice=Stall) per stall episode for a
    human to act on (the append-only authorship path, the RunDebriefer stance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# ProcedureWatcher agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the other seeded
# agents: changing this orphans every prior ProcedureWatcher-authored Decision
# (their actor_id pointers go stale). UUID is in the deployment-controlled
# `0c0c` block (eighth seeded identity).
PROCEDURE_WATCHER_AGENT_ID = UUID("01900000-0000-7000-8000-00000c0c0010")
PROCEDURE_WATCHER_AGENT_NAME = "ProcedureWatcher"
PROCEDURE_WATCHER_AGENT_KIND = "ProcedureWatcher"
PROCEDURE_WATCHER_AGENT_VERSION = "1.0.0"
PROCEDURE_WATCHER_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: watches in-conduct procedures (Running / Held) "
    "and records one Decision(context=ProcedureProgress, choice=Stall) per "
    "procedure that has sat past the staleness window without progressing. For a "
    "Running candidate it folds in the latest activity recorded_at first, so an "
    "actively-logging conduct is not falsely flagged. Flag-only (advise a "
    "human); issues no command."
)


# Sentinel model ref: ProcedureWatcher is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an LLM
# (the runtime is a periodic staleness comparison, no build_llm call).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:ProcedureWatcher:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000c0c0014")


async def seed_procedure_watcher_agent(kernel: Kernel) -> None:
    """Seed the ProcedureWatcher Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=PROCEDURE_WATCHER_AGENT_ID,
        name=PROCEDURE_WATCHER_AGENT_NAME,
        kind=PROCEDURE_WATCHER_AGENT_KIND,
        version=PROCEDURE_WATCHER_AGENT_VERSION,
        description=PROCEDURE_WATCHER_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedProcedureWatcherAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "PROCEDURE_WATCHER_AGENT_DESCRIPTION",
    "PROCEDURE_WATCHER_AGENT_ID",
    "PROCEDURE_WATCHER_AGENT_KIND",
    "PROCEDURE_WATCHER_AGENT_NAME",
    "PROCEDURE_WATCHER_AGENT_VERSION",
    "seed_procedure_watcher_agent",
]
