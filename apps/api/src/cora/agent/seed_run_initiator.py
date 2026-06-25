"""Bootstrap-time seed for the RunInitiator Agent.

The RunInitiator is the agent that STARTS Runs autonomously (proactive
creation), distinct from the RunSupervisor, which watches an in-flight Run
and holds / resumes it (reactive lifecycle protection). It needs an Agent
record (and its co-registered Actor) to exist at the pinned
`RUN_INITIATOR_AGENT_ID` so it can author Decisions
(`decided_by = ActorId(RUN_INITIATOR_AGENT_ID)`) and issue `start_run` as
an agent-kind principal. Mirrors `cora.agent.seed_run_supervisor` verbatim
except for the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

  - Pinned UUID in the `111100XX` range (seventh deployment agent; the
    repeated-quad scheme continued into the numeric range now that the
    `aaaa`-`ffff` letter blocks are taken). Deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`). The model_ref is never used to build an
    LLM (the runtime is a separate entry point, not an LLM subscriber); it
    only satisfies the Agent aggregate's required field.
  - Authorization: the runtime issues `start_run` through the Authorize
    port like any principal. Under the default AllowAllAuthorize it is
    permitted; under TrustAuthorize the operator's single configured Policy
    must include this principal + {StartRun} (least authority: the start
    grant stays isolated to this principal, not folded into the
    RunSupervisor's hold / resume grants). No separate Policy is seeded:
    TrustAuthorize evaluates exactly ONE configured policy, so a separate
    RunInitiator policy would never be consulted (it is operator-config,
    not seed config).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunInitiator agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_SUPERVISOR_AGENT_ID`: changing this orphans every prior
# RunInitiator-authored Decision (their actor_id pointers go stale). UUID is
# in the deployment-controlled `111100XX` range (seventh agent), keeping the
# bootstrap constants visually grouped per agent.
RUN_INITIATOR_AGENT_ID = UUID("01900000-0000-7000-8000-000011110010")
RUN_INITIATOR_AGENT_NAME = "RunInitiator"
RUN_INITIATOR_AGENT_KIND = "RunInitiator"
RUN_INITIATOR_AGENT_VERSION = "1.0.0"
RUN_INITIATOR_AGENT_DESCRIPTION = (
    "Deterministic agent that autonomously STARTS Runs: it records one "
    "Decision(context=RunInitiation, choice=Start) and issues start_run as "
    "an agent principal through the same authorized path a human uses "
    "(trigger_source=RunInitiator, linked via decided_by_decision_id). It "
    "does not supervise in-flight Runs (that is the RunSupervisor); it "
    "creates them. The start-safety envelope still gates every start, so it "
    "is not a safety bypass (the floor PSS owns hard safety)."
)


# Sentinel model ref: RunInitiator is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build an
# LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:RunInitiator:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000011110012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000011110013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000011110014")


async def seed_run_initiator_agent(kernel: Kernel) -> None:
    """Seed the RunInitiator Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_INITIATOR_AGENT_ID,
        name=RUN_INITIATOR_AGENT_NAME,
        kind=RUN_INITIATOR_AGENT_KIND,
        version=RUN_INITIATOR_AGENT_VERSION,
        description=RUN_INITIATOR_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunInitiatorAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_INITIATOR_AGENT_DESCRIPTION",
    "RUN_INITIATOR_AGENT_ID",
    "RUN_INITIATOR_AGENT_KIND",
    "RUN_INITIATOR_AGENT_NAME",
    "RUN_INITIATOR_AGENT_VERSION",
    "seed_run_initiator_agent",
]
