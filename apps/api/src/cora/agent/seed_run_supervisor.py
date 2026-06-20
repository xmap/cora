"""Bootstrap-time seed for the RunSupervisor Agent.

The RunSupervisor runtime (CORA's first ACTIVE in-loop agent) needs an
Agent record (and its co-registered Actor) to exist at the pinned
`RUN_SUPERVISOR_AGENT_ID` so it can author Decisions
(`decided_by = ActorId(RUN_SUPERVISOR_AGENT_ID)`) and issue Run
lifecycle commands as an agent-kind principal. Mirrors
`cora.agent.seed.seed_run_debriefer_agent` verbatim except for the
per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

Per [[project-run-supervisor-design]]:
  - Pinned UUID in the `cccc00XX` range (third agent, sibling to the
    RunDebriefer `aaaa00XX` and CautionDrafter `bbbb00XX` ranges);
    deployment-stable forever.
  - DETERMINISTIC agent (rule-based, NOT LLM): no prompt template
    (`prompt_template_id=None`) and a sentinel `ModelRef`
    (`provider="deterministic"`). The model_ref is never used to build
    an LLM (the runtime is a separate periodic loop, not an LLM
    subscriber); it only satisfies the Agent aggregate's required
    field. Watch: the Agent aggregate is LLM-shaped; revisit a
    first-class deterministic-agent shape if more rule-agents land.
  - Authorization: the runtime issues commands through the Authorize
    port like any principal. Under the default AllowAllAuthorize it is
    permitted; under TrustAuthorize the operator's single configured
    Policy must include this principal + {HoldRun, StopRun, AbortRun}.
    No separate Policy is seeded: TrustAuthorize evaluates exactly ONE
    configured policy, so a separate RunSupervisor policy would never be
    consulted (it is operator-config, not seed config).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import ModelRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunSupervisor agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_DEBRIEFER_AGENT_ID` / `CAUTION_DRAFTER_AGENT_ID`: changing this
# orphans every prior RunSupervisor-authored Decision (their actor_id
# pointers go stale). UUID is in the deployment-controlled `cccc00XX`
# range (third agent), keeping the bootstrap constants visually grouped
# per agent.
RUN_SUPERVISOR_AGENT_ID = UUID("01900000-0000-7000-8000-0000cccc0010")
RUN_SUPERVISOR_AGENT_NAME = "RunSupervisor"
RUN_SUPERVISOR_AGENT_KIND = "RunSupervisor"
RUN_SUPERVISOR_AGENT_VERSION = "1.0.0"
RUN_SUPERVISOR_AGENT_DESCRIPTION = (
    "Deterministic in-loop agent: watches an in-flight Run and issues "
    "hold_run / stop_run / abort_run when a wind-down rule fires, recording "
    "one Decision(context=RunSupervision) per disposition. Wind-down only; "
    "not a safety interlock (the floor PSS owns hard safety)."
)


# Sentinel model ref: RunSupervisor is rule-based, not an LLM agent. The
# Agent aggregate requires a ModelRef; this value is never used to build
# an LLM (no subscriber / no build_llm call for this agent).
_DETERMINISTIC_MODEL_REF = ModelRef(
    provider="deterministic",
    model="agent:RunSupervisor:v1",
    snapshot_pin=None,
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000cccc0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000cccc0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000cccc0014")


async def seed_run_supervisor_agent(kernel: Kernel) -> None:
    """Seed the RunSupervisor Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=RUN_SUPERVISOR_AGENT_ID,
        name=RUN_SUPERVISOR_AGENT_NAME,
        kind=RUN_SUPERVISOR_AGENT_KIND,
        version=RUN_SUPERVISOR_AGENT_VERSION,
        description=RUN_SUPERVISOR_AGENT_DESCRIPTION,
        model_ref=_DETERMINISTIC_MODEL_REF,
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedRunSupervisorAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "RUN_SUPERVISOR_AGENT_DESCRIPTION",
    "RUN_SUPERVISOR_AGENT_ID",
    "RUN_SUPERVISOR_AGENT_KIND",
    "RUN_SUPERVISOR_AGENT_NAME",
    "RUN_SUPERVISOR_AGENT_VERSION",
    "seed_run_supervisor_agent",
]
