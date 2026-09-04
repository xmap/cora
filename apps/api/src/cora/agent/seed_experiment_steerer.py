"""Bootstrap-time seed for the ExperimentSteerer Agent.

The ExperimentSteerer is CORA's L3 coordination agent for autonomous
experimentation: it owns a steered experiment ACROSS more than one Procedure.
The within-procedure steering loop (`conduct_until_advised`) already audits each
iteration's advice on `ProcedureIterationEnded`; the ExperimentSteerer's distinct
job is the across-procedure disposition (steer another Procedure, conclude, or
hold the campaign), recorded as a `Decision(context=ExperimentSteering)` via the
signed agent-write path (`cora.api._experiment_steerer`).

This seed gives the agent an Agent record (and its co-registered Actor) at the
pinned `EXPERIMENT_STEERER_AGENT_ID` so it can author Decisions
(`decided_by = ActorId(EXPERIMENT_STEERER_AGENT_ID)`) and issue follow-on
commands as an agent-kind principal. Mirrors
`cora.agent.seed_run_supervisor.seed_run_supervisor_agent` verbatim except for
the per-agent constants below; the shared scaffolding lives in
`cora.agent._agent_seed`.

  - Pinned UUID in the `5733XXXX` range (a fresh deployment-stable range,
    sibling to RunDebriefer `aaaa`, CautionDrafter `bbbb`, RunSupervisor `cccc`,
    etc.); deployment-stable forever. Changing it orphans every prior
    ExperimentSteerer-authored Decision.
  - DETERMINISTIC agent (the steering brain is the DecidePort, NOT an LLM): no
    prompt template (`prompt_template_id=None`) and a Rule brain
    (`BrainRef.for_rule("ExperimentSteerer:v1")`). Same posture as RunSupervisor
    / RunInitiator.

    The rule is this agent's OWN logic, the across-procedure disposition, and
    it is genuinely fixed in this repo. The DecidePort is one altitude down: a
    tool the rule consults, whose substrate (`in_memory`, `grid_walk`, `sobol`,
    `botorch`, `staged`, `llm`) is deployment config and can differ per
    iteration. Which substrate actually advised therefore belongs on the
    per-iteration record, not here, where it would be a claim about the agent
    that the next deployment falsifies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.agent._agent_seed import AgentSeedIdentity, seed_agent
from cora.agent.aggregates.agent import BrainRef

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# ExperimentSteerer agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as the sibling agents:
# changing this orphans every prior ExperimentSteerer-authored Decision (their
# actor_id pointers go stale). UUID is in the deployment-controlled `5733XXXX`
# range (a fresh range distinct from the existing aaaa/bbbb/cccc/dddd/eeee/ffff/
# 1111/0c0c/ca11/cab1 agent ranges), keeping the bootstrap constants visually
# grouped per agent.
EXPERIMENT_STEERER_AGENT_ID = UUID("01900000-0000-7000-8000-000057330010")
EXPERIMENT_STEERER_AGENT_NAME = "ExperimentSteerer"
EXPERIMENT_STEERER_AGENT_KIND = "ExperimentSteerer"
EXPERIMENT_STEERER_AGENT_VERSION = "1.0.0"
EXPERIMENT_STEERER_AGENT_DESCRIPTION = (
    "Deterministic L3 coordination agent for autonomous experimentation: owns a "
    "steered experiment across more than one Procedure. The within-procedure "
    "steering loop (conduct_until_advised) audits each iteration on the "
    "iteration ledger; this agent records the across-procedure disposition "
    "(Continue / Conclude / Hold) as one Decision(context=ExperimentSteering) per "
    "step, linking any follow-on hold via decided_by_decision_id. The steering "
    "brain is the DecidePort, not an LLM."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-000057330012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-000057330013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-000057330014")


async def seed_experiment_steerer_agent(kernel: Kernel) -> None:
    """Seed the ExperimentSteerer Agent + co-registered Actor (idempotent)."""
    identity = AgentSeedIdentity(
        agent_id=EXPERIMENT_STEERER_AGENT_ID,
        name=EXPERIMENT_STEERER_AGENT_NAME,
        kind=EXPERIMENT_STEERER_AGENT_KIND,
        version=EXPERIMENT_STEERER_AGENT_VERSION,
        description=EXPERIMENT_STEERER_AGENT_DESCRIPTION,
        brain=BrainRef.for_rule("ExperimentSteerer:v1"),
        prompt_template_id=None,
        agent_event_id=_AGENT_EVENT_ID,
        actor_event_id=_ACTOR_EVENT_ID,
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        command_name="SeedExperimentSteererAgent",
    )
    await seed_agent(kernel, identity)


__all__ = [
    "EXPERIMENT_STEERER_AGENT_DESCRIPTION",
    "EXPERIMENT_STEERER_AGENT_ID",
    "EXPERIMENT_STEERER_AGENT_KIND",
    "EXPERIMENT_STEERER_AGENT_NAME",
    "EXPERIMENT_STEERER_AGENT_VERSION",
    "seed_experiment_steerer_agent",
]
